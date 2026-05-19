from __future__ import annotations

import logging
from collections import deque
from dataclasses import dataclass, field, replace

from cogames.policy.starter_agent import StarterCogPolicyImpl, StarterCogState
from mettagrid.policy.policy import StatefulPolicyImpl
from mettagrid.policy.policy_env_interface import PolicyEnvInterface
from mettagrid.simulator import Action
from mettagrid.simulator.interface import AgentObservation

logger = logging.getLogger("cogames.policy.aligner_agent")

Coord = tuple[int, int]
_DIRECTION_DELTAS: tuple[tuple[str, Coord], ...] = (
    ("north", (-1, 0)),
    ("east", (0, 1)),
    ("south", (1, 0)),
    ("west", (0, -1)),
)
_DIRECTION_DELTA_MAP: dict[str, Coord] = {name: delta for name, delta in _DIRECTION_DELTAS}
_HUB_SEARCH_DISTANCE = 20
_HUB_ALIGN_DISTANCE = 25
_JUNCTION_ALIGN_DISTANCE = 15

# HP retreat: retreat to friendly territory when HP drops below this fraction of max
# Issue-36 v4: increased from 0.50 to 0.70 — at 50%, agents only have 49 steps
# to reach hub (1 HP/step drain). If hub is >49 cells away, they die.
# At 70%, agents have 69 steps to reach hub, which is much more forgiving.
_HP_RETREAT_THRESHOLD = 0.70
# Distance from hub/junction to be considered "in friendly territory".
# Game engine territory: hub=20, junction=10. Use conservative margins.
_HUB_TERRITORY_DISTANCE = 15
_JUNCTION_TERRITORY_DISTANCE = 10


class SharedMap:
    """Shared map knowledge across all agents in the same team.

    A single SharedMap instance is created by the MultiAgentPolicy and passed
    to every agent.  Each agent's _update_map_memory writes to these sets,
    so one agent's exploration instantly benefits all others' BFS.
    """

    def __init__(self) -> None:
        # Core BFS graph
        self.known_free_cells: set[Coord] = set()
        self.blocked_cells: set[Coord] = set()
        self.move_blocked_cells: set[Coord] = set()
        # Structures (static — once seen, remembered forever)
        self.known_hubs: set[Coord] = set()
        self.known_aligner_stations: set[Coord] = set()
        self.known_miner_stations: set[Coord] = set()
        self.known_hazard_stations: set[Coord] = set()
        self.known_extractors: set[Coord] = set()
        # Junctions (dynamic — refreshed per visible area)
        self.known_neutral_junctions: set[Coord] = set()
        self.known_friendly_junctions: set[Coord] = set()
        self.known_enemy_junctions: set[Coord] = set()
        # Agent gear tracking for team coordination
        self.agent_gears: dict[int, str] = {}
        # Agent position tracking for congestion avoidance (issue-35)
        self.agent_positions: dict[int, Coord] = {}
        # Hub depletion tracking (issue-16): count total hearts withdrawn across team
        self.hub_hearts_withdrawn: int = 0
        # Issue-36: deposit tracking for heart pipeline awareness
        self.total_deposits: dict[str, int] = {"carbon": 0, "oxygen": 0, "germanium": 0, "silicon": 0}
        self.hearts_crafted_estimate: int = 0  # estimated hearts created by make_heart
        # Issue-36 v16: aligner junction coordination — track which junction each aligner
        # is targeting so other aligners avoid picking the same one.
        self.aligner_targets: dict[int, Coord | None] = {}
        # Issue-36 v18: heart queue management — track which aligners are en route to get hearts.
        # Prevents all aligners from rushing to hub when only 1-2 hearts are available.
        self.agents_getting_hearts: set[int] = set()
        self.hub_deposits_total: int = 0
        # Issue-47: track active miner IDs for adaptive return_load
        self.active_miner_ids: set[int] = set()
        # Issue-36 v20: shared per-element extractor locations. When one miner discovers
        # a silicon extractor, all miners immediately know where it is. Critical for
        # team_scarce_element (V15) — without shared data, a miner told to mine silicon
        # can't find the extractor if it hasn't visited one yet.
        self.extractors_by_element: dict[str, set[Coord]] = {
            e: set() for e in ("carbon", "oxygen", "germanium", "silicon")
        }
        self.depleted_extractors: set[Coord] = set()
        self.miner_targets: dict[int, Coord | None] = {}


@dataclass
class AlignerState(StarterCogState):
    last_mode: str = "bootstrap"
    known_free_cells: set[Coord] = field(default_factory=set)
    blocked_cells: set[Coord] = field(default_factory=set)
    known_hubs: set[Coord] = field(default_factory=set)
    known_aligner_stations: set[Coord] = field(default_factory=set)
    known_neutral_junctions: set[Coord] = field(default_factory=set)
    known_friendly_junctions: set[Coord] = field(default_factory=set)
    known_enemy_junctions: set[Coord] = field(default_factory=set)
    known_hazard_stations: set[Coord] = field(default_factory=set)
    verified_aligner_stations: set[Coord] = field(default_factory=set)
    verified_hubs: set[Coord] = field(default_factory=set)
    # Track last attempted move to detect impassable objects on move failure
    last_pos: Coord | None = None
    last_move_target: Coord | None = None
    # Cells blocked by move failure (not cleared by observation updates)
    move_blocked_cells: set[Coord] = field(default_factory=set)
    # Issue-44: per-agent move cooldown to break congestion deadlocks
    move_cooldowns: dict[Coord, int] = field(default_factory=dict)
    steps_since_last_move: int = 0
    # Junctions permanently skipped after repeated navigation failures
    blacklisted_junctions: set[Coord] = field(default_factory=set)
    # Issue-65: cells where gear contamination occurred — added to BFS avoid set
    contamination_avoid_cells: set[Coord] = field(default_factory=set)
    gear_contamination_count: int = 0


class AlignerPolicyImpl(StatefulPolicyImpl[AlignerState]):
    def __init__(self, policy_env_info: PolicyEnvInterface, agent_id: int, shared_map: SharedMap | None = None):
        self._starter = StarterCogPolicyImpl(policy_env_info, agent_id, preferred_gear="aligner")
        self._agent_id = agent_id
        self._shared_map = shared_map
        self._team_tag = self._tag_id("team:cogs")
        self._net_tag = self._tag_id("net:cogs")
        self._enemy_team_tag = self._tag_id("team:clips")
        self._enemy_net_tag = self._tag_id("net:clips")
        self._hub_tags = self._starter._resolve_tag_ids(["hub"])
        self._junction_tags = self._starter._resolve_tag_ids(["junction"])
        self._aligner_station_tags = self._starter._resolve_tag_ids(self._gear_station_names(policy_env_info.tags))
        self._hazard_station_tags = self._resolve_non_aligner_station_tags(policy_env_info)
        self._wall_tags = self._starter._resolve_tag_ids(["wall"])
        # Issue-36 v8: track extractors as blocked for navigation (they block movement)
        self._extractor_tags = self._starter._extractor_tags
        self._obs_radius_row = self._starter._center[0]
        self._obs_radius_col = self._starter._center[1]

    def _tag_id(self, name: str) -> int | None:
        return self._starter._tag_name_to_id.get(name)

    def _gear_station_names(self, all_tags: list[str]) -> list[str]:
        names = {"aligner_station"}
        for tag_name in all_tags:
            if not tag_name.startswith("type:"):
                continue
            object_name = tag_name.removeprefix("type:")
            if object_name == "aligner" or object_name.endswith(":aligner"):
                names.add(object_name)
        return sorted(names)

    def _resolve_non_aligner_station_tags(self, policy_env_info: PolicyEnvInterface) -> set[int]:
        other_gear = ("miner", "scrambler", "scout")
        names: set[str] = set()
        for gear in other_gear:
            names.add(f"{gear}_station")
            for tag_name in policy_env_info.tags:
                if not tag_name.startswith("type:"):
                    continue
                object_name = tag_name.removeprefix("type:")
                if object_name.endswith(f":{gear}") or object_name == gear:
                    names.add(object_name)
        return self._starter._resolve_tag_ids(sorted(names))

    def _bind_shared_map(self, state: AlignerState) -> None:
        """Point state's map fields at the SharedMap sets so all agents share one map."""
        sm = self._shared_map
        if sm is None:
            return
        state.known_free_cells = sm.known_free_cells
        state.blocked_cells = sm.blocked_cells
        state.move_blocked_cells = sm.move_blocked_cells
        state.known_hubs = sm.known_hubs
        state.known_aligner_stations = sm.known_aligner_stations
        state.known_neutral_junctions = sm.known_neutral_junctions
        state.known_friendly_junctions = sm.known_friendly_junctions
        state.known_enemy_junctions = sm.known_enemy_junctions
        state.known_hazard_stations = sm.known_hazard_stations

    def initial_agent_state(self) -> AlignerState:
        starter_state = self._starter.initial_agent_state()
        state = AlignerState(
            wander_direction_index=starter_state.wander_direction_index,
            wander_steps_remaining=starter_state.wander_steps_remaining,
        )
        self._bind_shared_map(state)
        return state

    def _spawn_offset(self, obs: AgentObservation) -> Coord:
        row = 0
        col = 0
        for token in obs.tokens:
            name = token.feature.name
            value = int(token.value)
            if name == "lp:north":
                row -= value
            elif name == "lp:south":
                row += value
            elif name == "lp:east":
                col += value
            elif name == "lp:west":
                col -= value
        return row, col

    def _visible_abs_cell(self, current_abs: Coord, location: Coord) -> Coord:
        return (
            current_abs[0] + (location[0] - self._starter._center[0]),
            current_abs[1] + (location[1] - self._starter._center[1]),
        )

    def _visible_abs_cells(self, current_abs: Coord) -> set[Coord]:
        cells: set[Coord] = set()
        for d_row in range(-self._obs_radius_row, self._obs_radius_row + 1):
            for d_col in range(-self._obs_radius_col, self._obs_radius_col + 1):
                cells.add((current_abs[0] + d_row, current_abs[1] + d_col))
        return cells

    def _neighbors(self, cell: Coord) -> list[tuple[str, Coord]]:
        return [(name, (cell[0] + delta[0], cell[1] + delta[1])) for name, delta in _DIRECTION_DELTAS]

    def _ordered_neighbors_toward(self, cell: Coord, goal: Coord) -> list[tuple[str, Coord]]:
        return sorted(
            self._neighbors(cell),
            key=lambda item: (
                abs(item[1][0] - goal[0]) + abs(item[1][1] - goal[1]),
                item[0] != "west",
                item[0] != "east",
                item[0] != "north",
                item[0] != "south",
            ),
        )

    def _nearest_known(self, current_abs: Coord, candidates: set[Coord]) -> Coord | None:
        if not candidates:
            return None
        return min(candidates, key=lambda coord: (abs(coord[0] - current_abs[0]) + abs(coord[1] - current_abs[1]), coord))

    def _bfs_first_direction(self, state: AlignerState, start: Coord, goal: Coord, avoid_hazards: bool = True) -> str | None:
        if start == goal:
            return self._starter._fallback_action_name
        if goal not in state.known_free_cells:
            return None
        avoid = ((state.known_hazard_stations | state.contamination_avoid_cells) - {goal}) if avoid_hazards else set()
        frontier: deque[Coord] = deque([start])
        parents: dict[Coord, tuple[Coord, str] | None] = {start: None}
        while frontier:
            cell = frontier.popleft()
            if cell == goal:
                break
            for direction, neighbor in self._ordered_neighbors_toward(cell, goal):
                if neighbor in parents or neighbor not in state.known_free_cells or neighbor in avoid:
                    continue
                parents[neighbor] = (cell, direction)
                frontier.append(neighbor)
        if goal not in parents:
            return None
        step = goal
        while parents[step] is not None and parents[step][0] != start:
            step = parents[step][0]
        if parents[step] is None:
            return None
        return parents[step][1]

    def _bfs_without_cooldowns(self, state: AlignerState, start: Coord, goal: Coord, avoid_hazards: bool = True) -> str | None:
        """BFS ignoring cooldown-blocked cells. Cooldowns are transient (agent collisions) and may
        have cleared by the time we reach them."""
        cooldown_cells = set(state.move_cooldowns.keys())
        if not cooldown_cells:
            return None
        saved_blocked = state.blocked_cells
        saved_free = state.known_free_cells
        state.blocked_cells = saved_blocked - cooldown_cells
        state.known_free_cells = saved_free | cooldown_cells
        direction = self._bfs_first_direction(state, start, goal, avoid_hazards=avoid_hazards)
        state.blocked_cells = saved_blocked
        state.known_free_cells = saved_free
        return direction

    def _bfs_optimistic_direction(self, state: AlignerState, start: Coord, goal: Coord, avoid_hazards: bool = True, max_cells: int = 20000) -> str | None:
        """Optimistic BFS: treat unknown cells as traversable (only avoids known walls/hazards).
        Useful when the path to goal goes through unexplored territory."""
        if start == goal:
            return self._starter._fallback_action_name
        avoid = ((state.known_hazard_stations | state.contamination_avoid_cells) - {goal}) if avoid_hazards else set()
        frontier: deque[Coord] = deque([start])
        parents: dict[Coord, tuple[Coord, str] | None] = {start: None}
        while frontier and len(parents) < max_cells:
            cell = frontier.popleft()
            if cell == goal:
                break
            for direction, neighbor in self._ordered_neighbors_toward(cell, goal):
                if neighbor in parents or neighbor in state.blocked_cells or neighbor in avoid:
                    continue
                parents[neighbor] = (cell, direction)
                frontier.append(neighbor)
        if goal not in parents:
            return None
        step = goal
        while parents[step] is not None and parents[step][0] != start:
            step = parents[step][0]
        if parents[step] is None:
            return None
        return parents[step][1]

    def _best_approach_cell(self, state: AlignerState, current_abs: Coord, blocked_target: Coord, preferred_side: int | None = None) -> Coord | None:
        """Find the best adjacent cell to a blocked target (e.g., a station object) to navigate toward.

        Returns the adjacent cell closest to current_abs that is not in blocked_cells.
        If preferred_side is given (0=N, 1=E, 2=S, 3=W), prefer that side first."""
        approach_candidates = []
        for i, (_, (dr, dc)) in enumerate(_DIRECTION_DELTAS):
            neighbor = (blocked_target[0] + dr, blocked_target[1] + dc)
            if neighbor not in state.blocked_cells:
                approach_candidates.append((i, neighbor))
        if not approach_candidates:
            return None
        if preferred_side is not None:
            approach_candidates.sort(key=lambda ic: (
                (ic[0] - preferred_side) % 4,
                abs(ic[1][0] - current_abs[0]) + abs(ic[1][1] - current_abs[1]),
            ))
            return approach_candidates[0][1]
        return min((c for _, c in approach_candidates), key=lambda c: abs(c[0] - current_abs[0]) + abs(c[1] - current_abs[1]))

    def _navigate_to_station(self, state: AlignerState, current_abs: Coord, station_abs: Coord, avoid_hazards: bool = True, preferred_side: int | None = None) -> str | None:
        """Navigate toward a station object (which is in blocked_cells).

        Targets the best adjacent cell to the station rather than the station itself."""
        approach = self._best_approach_cell(state, current_abs, station_abs, preferred_side=preferred_side)
        if approach is None:
            return None
        if current_abs == approach:
            # Already adjacent - try moving into station directly (triggers equip)
            dr = station_abs[0] - current_abs[0]
            dc = station_abs[1] - current_abs[1]
            if abs(dr) >= abs(dc):
                return "south" if dr > 0 else "north"
            return "east" if dc > 0 else "west"
        direction = self._bfs_first_direction(state, current_abs, approach, avoid_hazards=avoid_hazards)
        if direction is not None:
            return direction
        direction = self._bfs_without_cooldowns(state, current_abs, approach, avoid_hazards=avoid_hazards)
        if direction is not None:
            return direction
        direction = self._bfs_optimistic_direction(state, current_abs, approach, avoid_hazards=avoid_hazards)
        if direction is not None:
            return direction
        # Greedy toward the approach cell, avoiding known obstacles
        candidates = []
        for dir_name, (ddr, ddc) in _DIRECTION_DELTAS:
            neighbor = (current_abs[0] + ddr, current_abs[1] + ddc)
            dist = abs(neighbor[0] - approach[0]) + abs(neighbor[1] - approach[1])
            hard_blocked = neighbor in state.blocked_cells
            soft_blocked = neighbor in state.move_blocked_cells
            candidates.append((hard_blocked, soft_blocked, dist, dir_name))
        candidates.sort()
        return candidates[0][3]

    def _safe_wander(self, state: AlignerState, current_abs: Coord) -> tuple[Action, AlignerState]:
        """Wander avoiding hazard stations and blocked cells (hard walls)."""
        hard_avoid = state.known_hazard_stations | state.blocked_cells | state.contamination_avoid_cells
        # First pass: avoid both hard blocks and move-blocked cells
        for i in range(4):
            idx = (state.wander_direction_index + i) % 4
            direction, (dr, dc) = _DIRECTION_DELTAS[idx]
            neighbor = (current_abs[0] + dr, current_abs[1] + dc)
            if neighbor not in hard_avoid and neighbor not in state.move_blocked_cells:
                state.wander_direction_index = (idx + 1) % 4
                return self._starter._action(f"move_{direction}"), state
        # Second pass: accept move-blocked (transient), still avoid hard blocks
        for i in range(4):
            idx = (state.wander_direction_index + i) % 4
            direction, (dr, dc) = _DIRECTION_DELTAS[idx]
            neighbor = (current_abs[0] + dr, current_abs[1] + dc)
            if neighbor not in hard_avoid:
                state.wander_direction_index = (idx + 1) % 4
                return self._starter._action(f"move_{direction}"), state
        # All blocked — cycle anyway
        state.wander_direction_index = (state.wander_direction_index + 1) % 4
        return self._starter._wander(state)

    def _move_target(self, current_abs: Coord, direction: str) -> Coord:
        """Compute the cell we'll be at if we move in `direction` from `current_abs`."""
        dr, dc = _DIRECTION_DELTA_MAP.get(direction, (0, 0))
        return (current_abs[0] + dr, current_abs[1] + dc)

    def _greedy_move_toward_abs(
        self,
        state: AlignerState,
        current_abs: Coord,
        target_abs: Coord,
        avoid_hazards: bool = False,
    ) -> tuple[Action, AlignerState]:
        """Move greedily toward a known absolute position, avoiding known obstacles.

        Ranks all 4 directions by: (0) hazard station if avoid_hazards,
        (1) hard-blocked (walls), (2) soft-blocked (move failures — may be
        transient agent collisions), (3) Manhattan distance.
        When avoid_hazards is True and all options are contaminated, falls back
        to safe_wander to escape (issue #12 + #25 multi-seed regression)."""
        candidates = []
        for dir_name, (ddr, ddc) in _DIRECTION_DELTAS:
            neighbor = (current_abs[0] + ddr, current_abs[1] + ddc)
            dist = abs(neighbor[0] - target_abs[0]) + abs(neighbor[1] - target_abs[1])
            is_hazard = (neighbor in state.known_hazard_stations or neighbor in state.contamination_avoid_cells) if avoid_hazards else False
            hard_blocked = neighbor in state.blocked_cells
            soft_blocked = neighbor in state.move_blocked_cells
            candidates.append((is_hazard, hard_blocked, soft_blocked, dist, dir_name))
        candidates.sort()
        if avoid_hazards and candidates[0][0]:
            # All greedy options contaminated — escape via safe_wander
            return self._safe_wander(state, current_abs)
        return self._starter._action(f"move_{candidates[0][4]}"), state

    def _move_to(self, state: AlignerState, current_abs: Coord, target_abs: Coord | None) -> tuple[Action, AlignerState]:
        if target_abs is None:
            return self._safe_wander(state, current_abs)
        direction = self._bfs_first_direction(state, current_abs, target_abs)
        if direction is None:
            direction = self._bfs_without_cooldowns(state, current_abs, target_abs)
        if direction is None:
            direction = self._bfs_optimistic_direction(state, current_abs, target_abs)
        if direction is None:
            return self._safe_wander(state, current_abs)
        return self._starter._action(f"move_{direction}"), state

    def _frontier_cells(self, state: AlignerState) -> set[Coord]:
        frontier: set[Coord] = set()
        for cell in state.known_free_cells:
            for _, neighbor in self._neighbors(cell):
                if neighbor not in state.known_free_cells and neighbor not in state.blocked_cells:
                    frontier.add(cell)
                    break
        return frontier

    def _frontier_near(self, state: AlignerState, anchors: set[Coord], max_anchor_distance: int) -> set[Coord]:
        frontier = self._frontier_cells(state)
        if not anchors:
            return frontier
        near_frontier: set[Coord] = set()
        for cell in frontier:
            if min(abs(cell[0] - anchor[0]) + abs(cell[1] - anchor[1]) for anchor in anchors) <= max_anchor_distance:
                near_frontier.add(cell)
        return near_frontier or frontier

    def _inventory_count(self, obs: AgentObservation, item: str) -> int:
        for token in obs.tokens:
            if token.location != self._starter._center:
                continue
            if token.feature.name == f"inv:{item}":
                return int(token.value)
        return 0

    def _current_gear(self, obs: AgentObservation) -> str | None:
        return self._starter._current_gear(self._starter._inventory_items(obs))

    def _remember_static_objects(self, target_set: set[Coord], current_values: set[Coord]) -> None:
        target_set.update(current_values)

    def _refresh_dynamic_objects(self, visible_cells: set[Coord], target_set: set[Coord], current_values: set[Coord]) -> None:
        target_set.difference_update(visible_cells)
        target_set.update(current_values)

    _MOVE_COOLDOWN = 6

    def _update_map_memory(self, obs: AgentObservation, state: AlignerState) -> Coord:
        current_abs = self._spawn_offset(obs)

        # Issue-44: track whether the agent actually moved
        moved = state.last_pos is not None and current_abs != state.last_pos
        if moved:
            state.steps_since_last_move = 0
        else:
            state.steps_since_last_move += 1

        # Issue-44: per-agent move cooldown to break congestion deadlocks.
        if state.last_pos is not None and state.last_move_target is not None:
            if current_abs == state.last_pos:
                if state.steps_since_last_move <= 12:
                    state.move_cooldowns[state.last_move_target] = self._MOVE_COOLDOWN
                state.move_blocked_cells.add(state.last_move_target)
        state.last_pos = current_abs
        state.last_move_target = None

        # Tick down cooldowns
        expired = [cell for cell, ttl in state.move_cooldowns.items() if ttl <= 1]
        for cell in expired:
            del state.move_cooldowns[cell]
        for cell in list(state.move_cooldowns):
            state.move_cooldowns[cell] -= 1

        visible_cells = self._visible_abs_cells(current_abs)
        visible_tag_ids_by_cell: dict[Coord, set[int]] = {}
        blocked_now: set[Coord] = set()
        hubs_now: set[Coord] = set()
        stations_now: set[Coord] = set()
        hazard_stations_now: set[Coord] = set()

        extractors_now: set[Coord] = set()
        for token in obs.tokens:
            if token.feature.name != "tag" or token.location is None:
                continue
            abs_cell = self._visible_abs_cell(current_abs, token.location)
            visible_tag_ids_by_cell.setdefault(abs_cell, set()).add(int(token.value))
            if token.value in self._wall_tags:
                blocked_now.add(abs_cell)
            if token.value in self._hub_tags:
                hubs_now.add(abs_cell)
            if token.value in self._aligner_station_tags:
                stations_now.add(abs_cell)
            if token.value in self._hazard_station_tags:
                hazard_stations_now.add(abs_cell)
            if token.value in self._extractor_tags:
                blocked_now.add(abs_cell)
                extractors_now.add(abs_cell)
            if token.value in self._hub_tags:
                blocked_now.add(abs_cell)
            if token.value in self._aligner_station_tags:
                blocked_now.add(abs_cell)
            if token.value in self._hazard_station_tags:
                blocked_now.add(abs_cell)

        neutral_now: set[Coord] = set()
        friendly_now: set[Coord] = set()
        enemy_now: set[Coord] = set()
        for abs_cell, tag_ids in visible_tag_ids_by_cell.items():
            if not (tag_ids & self._junction_tags):
                continue
            if (self._team_tag in tag_ids) or (self._net_tag in tag_ids):
                friendly_now.add(abs_cell)
            elif (self._enemy_team_tag in tag_ids) or (self._enemy_net_tag in tag_ids):
                enemy_now.add(abs_cell)
            else:
                neutral_now.add(abs_cell)

        state.blocked_cells.difference_update(visible_cells)
        state.blocked_cells.update(blocked_now)
        # Issue-44: use per-agent cooldowns + legacy move_blocked_cells
        visually_free = visible_cells - blocked_now
        state.move_blocked_cells.difference_update(visually_free)
        cooldown_cells = set(state.move_cooldowns.keys())
        state.blocked_cells.update(state.move_blocked_cells)
        state.blocked_cells.update(cooldown_cells)
        state.known_free_cells.update(visually_free - cooldown_cells)
        state.known_free_cells.difference_update(state.blocked_cells)
        state.known_free_cells.add(current_abs)

        self._remember_static_objects(state.known_hubs, hubs_now)
        if hubs_now:
            state.verified_hubs.update(hubs_now)
        self._remember_static_objects(state.known_aligner_stations, stations_now)
        if stations_now:
            state.known_hazard_stations.difference_update(stations_now)
        self._remember_static_objects(state.known_hazard_stations, hazard_stations_now)
        if self._shared_map is not None and extractors_now:
            self._shared_map.known_extractors.update(extractors_now)
        self._refresh_dynamic_objects(visible_cells, state.known_neutral_junctions, neutral_now)
        self._refresh_dynamic_objects(visible_cells, state.known_friendly_junctions, friendly_now)
        self._refresh_dynamic_objects(visible_cells, state.known_enemy_junctions, enemy_now)
        state.known_neutral_junctions.difference_update(state.known_friendly_junctions)
        state.known_neutral_junctions.difference_update(state.known_enemy_junctions)
        return current_abs

    def _log_mode(self, obs: AgentObservation, state: AlignerState, mode: str) -> None:
        if state.last_mode != mode:
            logger.info("agent=%s mode=%s", obs.agent_id, mode)
            state.last_mode = mode

    def _read_hp(self, obs: AgentObservation) -> int | None:
        """Read current HP from observation tokens.

        Intentionally returns None: the aligner's HP retreat logic
        causes rapid oscillation near territory boundaries. Aligners work better
        without HP retreat because they operate near/at junctions.
        """
        return None

    def _in_friendly_territory(self, current_abs: Coord, state: AlignerState) -> bool:
        """Check if agent is near hub or a friendly junction (safe from HP drain)."""
        for hub in state.known_hubs:
            if abs(current_abs[0] - hub[0]) + abs(current_abs[1] - hub[1]) <= _HUB_TERRITORY_DISTANCE:
                return True
        for fj in state.known_friendly_junctions:
            if abs(current_abs[0] - fj[0]) + abs(current_abs[1] - fj[1]) <= _JUNCTION_TERRITORY_DISTANCE:
                return True
        return False

    def _move_toward_target(
        self,
        state: AlignerState,
        current_abs: Coord,
        target_abs: Coord | None,
    ) -> tuple[Action, AlignerState]:
        if target_abs is None:
            return self._safe_wander(state, current_abs)
        direction = self._bfs_first_direction(state, current_abs, target_abs)
        if direction is not None:
            return self._starter._action(f"move_{direction}"), state

        frontier_cells = self._frontier_cells(state)
        if not frontier_cells:
            return self._safe_wander(state, current_abs)

        best_frontier = min(
            frontier_cells,
            key=lambda cell: (
                abs(cell[0] - target_abs[0]) + abs(cell[1] - target_abs[1]),
                abs(cell[0] - current_abs[0]) + abs(cell[1] - current_abs[1]),
                cell,
            ),
        )
        if current_abs == best_frontier:
            for direction_name, neighbor in sorted(
                self._neighbors(current_abs),
                key=lambda item: (
                    item[1] in state.blocked_cells,
                    item[1] in state.known_free_cells,
                    item[1] in state.known_hazard_stations,
                    abs(item[1][0] - target_abs[0]) + abs(item[1][1] - target_abs[1]),
                ),
            ):
                if neighbor in state.blocked_cells or neighbor in state.known_free_cells or neighbor in state.known_hazard_stations:
                    continue
                return self._starter._action(f"move_{direction_name}"), state
            return self._safe_wander(state, current_abs)
        return self._move_to(state, current_abs, best_frontier)

    def _explore_frontier(
        self,
        obs: AgentObservation,
        state: AlignerState,
        frontier_cells: set[Coord],
    ) -> tuple[Action, AlignerState]:
        self._log_mode(obs, state, "explore")
        current_abs = self._spawn_offset(obs)
        if current_abs in frontier_cells:
            for direction, neighbor in self._neighbors(current_abs):
                if neighbor in state.blocked_cells or neighbor in state.known_free_cells or neighbor in state.known_hazard_stations:
                    continue
                return self._starter._action(f"move_{direction}"), replace(state, last_mode=state.last_mode)
        sm = self._shared_map
        other_positions = []
        if sm is not None:
            for aid, pos in sm.agent_positions.items():
                if aid != obs.agent_id:
                    other_positions.append(pos)
        if other_positions and len(frontier_cells) > 1:
            def _spread_score(cell):
                own_dist = abs(cell[0] - current_abs[0]) + abs(cell[1] - current_abs[1])
                nearest_other = min(
                    (abs(cell[0] - p[0]) + abs(cell[1] - p[1]) for p in other_positions),
                    default=9999,
                )
                return own_dist - nearest_other * 0.3
            target_abs = min(frontier_cells, key=lambda c: (_spread_score(c), c))
        else:
            target_abs = self._nearest_known(current_abs, frontier_cells)
        action, next_state = self._move_to(state, current_abs, target_abs)
        return action, replace(next_state, last_mode=state.last_mode)

    def _explore(self, obs: AgentObservation, state: AlignerState) -> tuple[Action, AlignerState]:
        return self._explore_frontier(obs, state, self._frontier_cells(state))

    def _explore_near_hub(self, obs: AgentObservation, state: AlignerState) -> tuple[Action, AlignerState]:
        frontier_cells = self._frontier_near(state, state.known_hubs, max_anchor_distance=_HUB_SEARCH_DISTANCE)
        return self._explore_frontier(obs, state, frontier_cells)

    def _alignment_frontier_cells(self, state: AlignerState) -> set[Coord]:
        frontier = self._frontier_cells(state)
        if not frontier:
            return frontier

        hub_set = state.verified_hubs if state.verified_hubs else state.known_hubs
        aligned_network = set(hub_set) | set(state.known_friendly_junctions)
        if not aligned_network:
            return frontier

        vision_margin = max(self._obs_radius_row, self._obs_radius_col)
        hub_search_radius = _HUB_ALIGN_DISTANCE + vision_margin
        junction_search_radius = _JUNCTION_ALIGN_DISTANCE + vision_margin

        preferred_frontier = {
            cell
            for cell in frontier
            if any(
                (
                    anchor in hub_set
                    and abs(cell[0] - anchor[0]) + abs(cell[1] - anchor[1]) <= hub_search_radius
                )
                or (
                    anchor in state.known_friendly_junctions
                    and abs(cell[0] - anchor[0]) + abs(cell[1] - anchor[1]) <= junction_search_radius
                )
                for anchor in aligned_network
            )
        }
        return preferred_frontier or frontier

    def _explore_for_alignment(self, obs: AgentObservation, state: AlignerState) -> tuple[Action, AlignerState]:
        return self._explore_frontier(obs, state, self._alignment_frontier_cells(state))

    def _gear_up(self, obs: AgentObservation, state: AlignerState, current_abs: Coord) -> tuple[Action, AlignerState]:
        self._log_mode(obs, state, "gear_up")
        visible_target = self._starter._closest_tag_location(obs, self._aligner_station_tags)
        if visible_target is not None:
            target_abs = self._visible_abs_cell(current_abs, visible_target)
            state.known_aligner_stations.add(target_abs)
            state.verified_aligner_stations.add(target_abs)
            direction = self._navigate_to_station(state, current_abs, target_abs, avoid_hazards=True)
            if direction is None:
                direction = self._navigate_to_station(state, current_abs, target_abs, avoid_hazards=False)
            if direction is not None:
                return self._starter._action(f"move_{direction}"), replace(state, last_mode=state.last_mode)
            action, next_state = self._greedy_move_toward_abs(state, current_abs, target_abs, avoid_hazards=False)
            return action, replace(next_state, last_mode=state.last_mode)
        station_candidates = state.verified_aligner_stations if state.verified_aligner_stations else state.known_aligner_stations
        target_abs = self._nearest_known(current_abs, station_candidates) if station_candidates else None
        if target_abs is None:
            hub_set = state.verified_hubs if state.verified_hubs else state.known_hubs
            if hub_set:
                hub_center = self._nearest_known(current_abs, hub_set)
                expected_station = (hub_center[0] + 4, hub_center[1] - 3)
                direction = self._navigate_to_station(state, current_abs, expected_station, avoid_hazards=True)
                if direction is None:
                    direction = self._navigate_to_station(state, current_abs, expected_station, avoid_hazards=False)
                if direction is not None:
                    return self._starter._action(f"move_{direction}"), replace(state, last_mode=state.last_mode)
            return self._explore(obs, state)
        direction = self._navigate_to_station(state, current_abs, target_abs, avoid_hazards=True)
        if direction is None:
            direction = self._navigate_to_station(state, current_abs, target_abs, avoid_hazards=False)
        if direction is not None:
            return self._starter._action(f"move_{direction}"), replace(state, last_mode=state.last_mode)
        action, next_state = self._greedy_move_toward_abs(state, current_abs, target_abs, avoid_hazards=False)
        return action, replace(next_state, last_mode=state.last_mode)

    def _get_heart(self, obs: AgentObservation, state: AlignerState, current_abs: Coord) -> tuple[Action, AlignerState]:
        self._log_mode(obs, state, "get_heart")
        preferred_side = self._agent_id % 4
        visible_target = self._starter._closest_tag_location(obs, self._hub_tags)
        if visible_target is not None:
            target_abs = self._visible_abs_cell(current_abs, visible_target)
            direction = self._navigate_to_station(state, current_abs, target_abs, avoid_hazards=True, preferred_side=preferred_side)
            if direction is None:
                direction = self._navigate_to_station(state, current_abs, target_abs, avoid_hazards=False, preferred_side=preferred_side)
            if direction is not None:
                return self._starter._action(f"move_{direction}"), replace(state, last_mode=state.last_mode)
            action, next_state = self._greedy_move_toward_abs(state, current_abs, target_abs, avoid_hazards=True)
            return action, replace(next_state, last_mode=state.last_mode)
        hub_candidates = state.verified_hubs if state.verified_hubs else state.known_hubs
        target_abs = self._nearest_known(current_abs, hub_candidates)
        if target_abs is None:
            return self._explore(obs, state)
        direction = self._navigate_to_station(state, current_abs, target_abs, avoid_hazards=True, preferred_side=preferred_side)
        if direction is None:
            direction = self._navigate_to_station(state, current_abs, target_abs, avoid_hazards=False, preferred_side=preferred_side)
        if direction is not None:
            return self._starter._action(f"move_{direction}"), replace(state, last_mode=state.last_mode)
        action, next_state = self._greedy_move_toward_abs(state, current_abs, target_abs, avoid_hazards=True)
        return action, replace(next_state, last_mode=state.last_mode)

    def _cascade_priority_target(self, current_abs: Coord, candidates: set[Coord], state: AlignerState) -> Coord | None:
        if not candidates:
            return None
        hub_set = state.verified_hubs if state.verified_hubs else state.known_hubs
        hub = min(hub_set, key=lambda h: abs(h[0]) + abs(h[1])) if hub_set else None
        if hub is None:
            return self._nearest_known(current_abs, candidates)
        not_yet_alignable = state.known_neutral_junctions - candidates
        enemy_junctions = state.known_enemy_junctions
        friendly_junctions = state.known_friendly_junctions
        def score(j: Coord) -> float:
            travel = abs(j[0] - current_abs[0]) + abs(j[1] - current_abs[1])
            hub_dist = abs(j[0] - hub[0]) + abs(j[1] - hub[1])
            unlocks = sum(
                1 for t in not_yet_alignable
                if abs(t[0] - j[0]) + abs(t[1] - j[1]) <= _JUNCTION_ALIGN_DISTANCE
            )
            nearby_enemy = sum(
                1 for e in enemy_junctions
                if abs(e[0] - j[0]) + abs(e[1] - j[1]) <= _JUNCTION_ALIGN_DISTANCE
            )
            recapture = nearby_enemy * 3.0
            cluster = sum(
                1 for f in friendly_junctions
                if abs(f[0] - j[0]) + abs(f[1] - j[1]) <= _JUNCTION_ALIGN_DISTANCE
            )
            return travel + hub_dist * 0.2 - unlocks * 3.0 - recapture - cluster * 1.5
        return min(candidates, key=score)

    def _is_alignable(self, junction: Coord, state: AlignerState) -> bool:
        hubs = state.verified_hubs if state.verified_hubs else state.known_hubs
        for hub in hubs:
            if abs(junction[0] - hub[0]) + abs(junction[1] - hub[1]) <= _HUB_ALIGN_DISTANCE:
                return True
        for friendly in state.known_friendly_junctions:
            if abs(junction[0] - friendly[0]) + abs(junction[1] - friendly[1]) <= _JUNCTION_ALIGN_DISTANCE:
                return True
        return False

    def _align_neutral(self, obs: AgentObservation, state: AlignerState, current_abs: Coord) -> tuple[Action, AlignerState]:
        bl = state.blacklisted_junctions
        alignable = {j for j in state.known_neutral_junctions
                     if self._is_alignable(j, state) and j not in bl}
        target_abs = self._cascade_priority_target(current_abs, alignable, state)
        if target_abs is None:
            return self._explore_for_alignment(obs, state)
        self._log_mode(obs, state, "align_neutral")
        # Prefer a hazard-free path to the junction; only allow crossing scout/scrambler
        # stations when the clean path is unreachable. Walking through a wrong-role station
        # auto-equips that gear and drops aligner, which has been the dominant
        # mid-episode contamination path on seeds 43/44 (issue #12).
        direction = self._bfs_first_direction(state, current_abs, target_abs, avoid_hazards=True)
        if direction is None:
            direction = self._bfs_first_direction(state, current_abs, target_abs, avoid_hazards=False)
        if direction is None:
            direction = self._bfs_without_cooldowns(state, current_abs, target_abs, avoid_hazards=True)
        if direction is None:
            direction = self._bfs_without_cooldowns(state, current_abs, target_abs, avoid_hazards=False)
        if direction is not None:
            return self._starter._action(f"move_{direction}"), replace(state, last_mode=state.last_mode)
        # BFS failed: try optimistic BFS (treat unknown cells as traversable)
        direction = self._bfs_optimistic_direction(state, current_abs, target_abs, avoid_hazards=True)
        if direction is None:
            direction = self._bfs_optimistic_direction(state, current_abs, target_abs, avoid_hazards=False)
        if direction is not None:
            return self._starter._action(f"move_{direction}"), replace(state, last_mode=state.last_mode)
        # Last resort: greedy absolute navigation toward known junction position,
        # still refusing to step onto known hazard stations.
        action, next_state = self._greedy_move_toward_abs(state, current_abs, target_abs, avoid_hazards=True)
        return action, replace(next_state, last_mode=state.last_mode)

    def step_with_state(self, obs: AgentObservation, state: AlignerState) -> tuple[Action, AlignerState]:
        current_abs = self._update_map_memory(obs, state)
        heart_count = self._inventory_count(obs, "heart")
        _vhubs = state.verified_hubs if state.verified_hubs else state.known_hubs
        near_hub = any(
            abs(current_abs[0] - h[0]) + abs(current_abs[1] - h[1]) <= 2
            for h in _vhubs
        )
        want_more_hearts = heart_count > 0 and heart_count < 3 and near_hub
        if self._current_gear(obs) != "aligner":
            action, state = self._gear_up(obs, state, current_abs)
        elif heart_count <= 0 or want_more_hearts:
            action, state = self._get_heart(obs, state, current_abs)
        else:
            action, state = self._align_neutral(obs, state, current_abs)
        action_name = action.name if hasattr(action, "name") else ""
        if action_name.startswith("move_"):
            state.last_move_target = self._move_target(current_abs, action_name[len("move_"):])
        return action, state
