from __future__ import annotations

import logging
from collections import deque
from dataclasses import dataclass, field, replace

from cogames.policy.starter_agent import ELEMENTS, StarterCogPolicyImpl, StarterCogState
from mettagrid.policy.policy import StatefulPolicyImpl
from mettagrid.policy.policy_env_interface import PolicyEnvInterface
from mettagrid.simulator import Action
from mettagrid.simulator.interface import AgentObservation

logger = logging.getLogger("cogames.policy.llm_skills")

Coord = tuple[int, int]
_HUB_SEARCH_DISTANCE = 20
_HUB_EXTRACTOR_OFFSETS: tuple[Coord, ...] = ((-8, -8), (-8, 8), (8, -8), (8, 8))
_DIRECTION_DELTAS: tuple[tuple[str, Coord], ...] = (
    ("north", (-1, 0)),
    ("east", (0, 1)),
    ("south", (1, 0)),
    ("west", (0, -1)),
)


@dataclass
class MinerSkillState(StarterCogState):
    last_mode: str = "bootstrap"
    remembered_hub_row_from_spawn: int | None = None
    remembered_hub_col_from_spawn: int | None = None
    known_free_cells: set[Coord] = field(default_factory=set)
    blocked_cells: set[Coord] = field(default_factory=set)
    known_hubs: set[Coord] = field(default_factory=set)
    known_miner_stations: set[Coord] = field(default_factory=set)
    known_extractors: set[Coord] = field(default_factory=set)
    # Issue-16: per-element extractor locations for diverse mining
    extractors_by_element: dict[str, set[Coord]] = field(default_factory=lambda: {e: set() for e in ("carbon", "oxygen", "germanium", "silicon")})
    known_hazard_stations: set[Coord] = field(default_factory=set)
    verified_hubs: set[Coord] = field(default_factory=set)
    verified_extractors: set[Coord] = field(default_factory=set)
    verified_extractors_by_element: dict[str, set[Coord]] = field(default_factory=lambda: {e: set() for e in ("carbon", "oxygen", "germanium", "silicon")})
    # Move-failure tracking (same mechanism as AlignerState)
    last_pos: Coord | None = None
    last_move_target: Coord | None = None
    # Issue-44: per-agent move cooldown to break congestion deadlocks.
    move_cooldowns: dict[Coord, int] = field(default_factory=dict)
    steps_since_last_move: int = 0
    # Issue-44: extractor depletion tracking. When a miner spends too many steps
    # near an extractor without gaining resources, mark it as depleted.
    depleted_extractors: set[Coord] = field(default_factory=set)
    steps_near_extractor_no_gain: int = 0
    # HP tracking for miner survival (issue #40)
    max_hp_seen: int = 0
    retreating_to_hub: bool = False
    # Mining route optimization (issue #40)
    preferred_extractor: Coord | None = None
    # Stuck detection (issue #40): break out of unproductive loops
    steps_in_current_mode: int = 0
    stuck_explore_remaining: int = 0
    last_carried_total: int = 0
    # Hub approach diversification: each miner prefers a different side
    hub_approach_rotation: int = 0
    # Gear contamination tracking: rotation for approaching miner stations
    gear_up_approach_rotation: int = 0
    gear_contamination_count: int = 0
    contamination_avoid_cells: set[Coord] = field(default_factory=set)


class MinerSkillImpl(StatefulPolicyImpl[MinerSkillState]):
    """Bounded miner skills plus navigation primitives shared by scripted and LLM-controlled miners."""

    def __init__(self, policy_env_info: PolicyEnvInterface, agent_id: int, return_load: int, shared_map=None):
        self._starter = StarterCogPolicyImpl(policy_env_info, agent_id, preferred_gear="miner")
        self._shared_map = shared_map
        self._policy_env_info = policy_env_info
        self._hub_tags = self._starter._resolve_tag_ids(["hub"])
        miner_station_names = self._miner_station_names(policy_env_info)
        self._miner_station_tags = self._starter._resolve_tag_ids(miner_station_names)
        self._hazard_station_tags = self._resolve_non_miner_station_tags(policy_env_info, miner_station_names)
        self._wall_tags = self._starter._resolve_tag_ids(["wall"])
        # Issue-16: per-element extractor tags for diverse mining
        self._extractor_tags_by_element: dict[str, set[int]] = {
            element: self._starter._resolve_tag_ids([f"{element}_extractor"])
            for element in ELEMENTS
        }
        self._return_load = return_load
        self._obs_radius_row = self._starter._center[0]
        self._obs_radius_col = self._starter._center[1]
        self._junction_tags = self._starter._resolve_tag_ids(["junction"])
        self._team_tag = self._starter._tag_name_to_id.get("team:cogs")
        self._net_tag = self._starter._tag_name_to_id.get("net:cogs")
        self._enemy_team_tag = self._starter._tag_name_to_id.get("team:clips")
        self._enemy_net_tag = self._starter._tag_name_to_id.get("net:clips")

    def _miner_station_names(self, policy_env_info: PolicyEnvInterface) -> list[str]:
        names = {"miner_station"}
        for tag_name in policy_env_info.tags:
            if not tag_name.startswith("type:"):
                continue
            object_name = tag_name.removeprefix("type:")
            if object_name.endswith(":miner") or object_name == "miner":
                names.add(object_name)
        return sorted(names)

    def _resolve_non_miner_station_tags(self, policy_env_info: PolicyEnvInterface, miner_names: list[str]) -> set[int]:
        other_gear = ("aligner", "scrambler", "scout")
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

    def _bind_shared_map_miner(self, state: MinerSkillState) -> None:
        """Point miner state's map fields at SharedMap sets."""
        sm = self._shared_map
        if sm is None:
            return
        state.known_free_cells = sm.known_free_cells
        state.blocked_cells = sm.blocked_cells
        state.known_hubs = sm.known_hubs
        state.known_miner_stations = sm.known_miner_stations
        state.known_extractors = sm.known_extractors
        state.known_hazard_stations = sm.known_hazard_stations
        # Share per-element extractor locations so all miners know where each element is
        if hasattr(sm, "extractors_by_element"):
            state.extractors_by_element = sm.extractors_by_element

    def initial_agent_state(self) -> MinerSkillState:
        starter_state = self._starter.initial_agent_state()
        state = MinerSkillState(
            wander_direction_index=starter_state.wander_direction_index,
            wander_steps_remaining=starter_state.wander_steps_remaining,
        )
        self._bind_shared_map_miner(state)
        return state

    def _inventory_counts(self, obs: AgentObservation) -> dict[str, int]:
        counts: dict[str, int] = {}
        center = self._starter._center
        for token in obs.tokens:
            if token.location != center:
                continue
            name = token.feature.name
            if not name.startswith("inv:"):
                continue
            parts = name.split(":", 2)
            if len(parts) >= 2 and parts[1] in ELEMENTS:
                counts[parts[1]] = int(token.value)
        return counts

    def _carried_total(self, obs: AgentObservation) -> int:
        return sum(self._inventory_counts(obs).values())

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

    def _current_abs(self, obs: AgentObservation) -> Coord:
        return self._spawn_offset(obs)

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

    def _remember_static_objects(self, target_set: set[Coord], current_values: set[Coord]) -> None:
        target_set.update(current_values)

    def _remember_visible_hub(self, obs: AgentObservation, state: MinerSkillState) -> None:
        hub_set = state.verified_hubs if state.verified_hubs else state.known_hubs
        if not hub_set:
            return
        hub_row, hub_col = min(hub_set, key=lambda coord: abs(coord[0]) + abs(coord[1]))
        state.remembered_hub_row_from_spawn = hub_row
        state.remembered_hub_col_from_spawn = hub_col

    def _move_target(self, current_abs: Coord, direction: str) -> Coord:
        delta_map = {name: delta for name, delta in _DIRECTION_DELTAS}
        dr, dc = delta_map.get(direction, (0, 0))
        return (current_abs[0] + dr, current_abs[1] + dc)

    _MOVE_COOLDOWN = 6

    def _update_map_memory(self, obs: AgentObservation, state: MinerSkillState) -> None:
        current_abs = self._current_abs(obs)

        # Issue-44: track whether the agent actually moved this step
        moved = state.last_pos is not None and current_abs != state.last_pos
        if moved:
            state.steps_since_last_move = 0
        else:
            state.steps_since_last_move += 1

        # Issue-44: per-agent move cooldown instead of shared move_blocked_cells.
        # When a move fails because another agent occupies the cell, add a LOCAL
        # cooldown instead of writing to the shared map. This prevents the
        # add-then-immediately-clear cycle that caused infinite BFS loops.
        if state.last_pos is not None and state.last_move_target is not None:
            if current_abs == state.last_pos:
                # Only apply cooldown if agent is NOT structurally stuck.
                # When stuck for >12 steps, cooldowns become counterproductive
                # (blocking the only viable paths in tight corridors).
                if state.steps_since_last_move <= 12:
                    state.move_cooldowns[state.last_move_target] = self._MOVE_COOLDOWN
        state.last_pos = current_abs
        state.last_move_target = None

        # Tick down all cooldowns and remove expired ones
        expired = [cell for cell, ttl in state.move_cooldowns.items() if ttl <= 1]
        for cell in expired:
            del state.move_cooldowns[cell]
        for cell in list(state.move_cooldowns):
            state.move_cooldowns[cell] -= 1

        visible_cells = self._visible_abs_cells(current_abs)
        blocked_now: set[Coord] = set()
        hubs_now: set[Coord] = set()
        miner_stations_now: set[Coord] = set()
        extractors_now: set[Coord] = set()
        hazard_stations_now: set[Coord] = set()

        visible_tag_ids_by_cell: dict[Coord, set[int]] = {}
        for token in obs.tokens:
            if token.feature.name != "tag" or token.location is None:
                continue
            abs_cell = self._visible_abs_cell(current_abs, token.location)
            visible_tag_ids_by_cell.setdefault(abs_cell, set()).add(int(token.value))
            if token.value in self._wall_tags:
                blocked_now.add(abs_cell)
            if token.value in self._hub_tags:
                hubs_now.add(abs_cell)
            if token.value in self._miner_station_tags:
                miner_stations_now.add(abs_cell)
            if token.value in self._starter._extractor_tags:
                extractors_now.add(abs_cell)
                for element, etags in self._extractor_tags_by_element.items():
                    if token.value in etags:
                        state.extractors_by_element[element].add(abs_cell)
            if token.value in self._hazard_station_tags:
                hazard_stations_now.add(abs_cell)

        sm = self._shared_map
        if sm is not None and self._junction_tags:
            for abs_cell, tag_ids in visible_tag_ids_by_cell.items():
                if not (tag_ids & self._junction_tags):
                    continue
                if (self._team_tag in tag_ids) or (self._net_tag in tag_ids):
                    sm.known_friendly_junctions.add(abs_cell)
                    sm.known_neutral_junctions.discard(abs_cell)
                    sm.known_enemy_junctions.discard(abs_cell)
                elif (self._enemy_team_tag in tag_ids) or (self._enemy_net_tag in tag_ids):
                    sm.known_enemy_junctions.add(abs_cell)
                    sm.known_neutral_junctions.discard(abs_cell)
                    sm.known_friendly_junctions.discard(abs_cell)
                else:
                    if abs_cell not in sm.known_friendly_junctions and abs_cell not in sm.known_enemy_junctions:
                        sm.known_neutral_junctions.add(abs_cell)

        blocked_now.update(extractors_now)
        blocked_now.update(hubs_now)
        blocked_now.update(miner_stations_now)
        blocked_now.update(hazard_stations_now)

        state.blocked_cells.difference_update(visible_cells)
        state.blocked_cells.update(blocked_now)
        # Issue-44: use per-agent cooldowns instead of shared move_blocked_cells.
        # Cooldown-blocked cells are added to blocked_cells for BFS avoidance.
        cooldown_cells = set(state.move_cooldowns.keys())
        state.blocked_cells.update(cooldown_cells)
        # Still clean up shared move_blocked_cells for aligners' benefit
        visually_free = visible_cells - blocked_now
        if self._shared_map and self._shared_map.move_blocked_cells:
            self._shared_map.move_blocked_cells.difference_update(visually_free)
        state.known_free_cells.update(visually_free - cooldown_cells)
        state.known_free_cells.difference_update(state.blocked_cells)
        state.known_free_cells.add(current_abs)

        self._remember_static_objects(state.known_hubs, hubs_now)
        if hubs_now:
            state.verified_hubs.update(hubs_now)
        self._remember_static_objects(state.known_miner_stations, miner_stations_now)
        self._remember_static_objects(state.known_extractors, extractors_now)
        if extractors_now:
            state.verified_extractors.update(extractors_now)
            for element, etags in self._extractor_tags_by_element.items():
                for abs_cell in extractors_now:
                    cell_tags = visible_tag_ids_by_cell.get(abs_cell, set())
                    if cell_tags & etags:
                        state.verified_extractors_by_element[element].add(abs_cell)
        self._remember_static_objects(state.known_hazard_stations, hazard_stations_now)
        self._remember_visible_hub(obs, state)

    def _safe_wander(self, state: MinerSkillState) -> tuple[Action, MinerSkillState]:
        """Wander avoiding hazard stations (non-miner stations) and blocked cells."""
        current_abs = (
            state.last_pos if state.last_pos is not None
            else (state.remembered_hub_row_from_spawn or 0, state.remembered_hub_col_from_spawn or 0)
        )
        hard_avoid = state.known_hazard_stations | state.blocked_cells | getattr(state, 'contamination_avoid_cells', set())
        for i in range(4):
            idx = (state.wander_direction_index + i) % 4
            direction, (dr, dc) = _DIRECTION_DELTAS[idx]
            neighbor = (current_abs[0] + dr, current_abs[1] + dc)
            if neighbor not in hard_avoid:
                state.wander_direction_index = (idx + 1) % 4
                return self._starter._action(f"move_{direction}"), state
        state.wander_direction_index = (state.wander_direction_index + 1) % 4
        return self._starter._wander(state)

    def _neighbors(self, cell: Coord) -> list[tuple[str, Coord]]:
        return [(name, (cell[0] + delta[0], cell[1] + delta[1])) for name, delta in _DIRECTION_DELTAS]

    def _nearest_known(self, current_abs: Coord, candidates: set[Coord]) -> Coord | None:
        if not candidates:
            return None
        return min(candidates, key=lambda coord: (abs(coord[0] - current_abs[0]) + abs(coord[1] - current_abs[1]), coord))

    def _nearest_extractor_hub_weighted(self, current_abs: Coord, candidates: set[Coord], state: MinerSkillState) -> Coord | None:
        if not candidates:
            return None
        hub_set = state.verified_hubs if state.verified_hubs else state.known_hubs
        if not hub_set:
            return self._nearest_known(current_abs, candidates)
        hub = min(hub_set, key=lambda h: abs(h[0]) + abs(h[1]))
        return min(candidates, key=lambda c: (
            abs(c[0] - current_abs[0]) + abs(c[1] - current_abs[1])
            + (abs(c[0] - hub[0]) + abs(c[1] - hub[1])) // 2,
            c,
        ))

    def _closest_visible_location(self, obs: AgentObservation, tag_ids: set[int]) -> Coord | None:
        return self._starter._closest_tag_location(obs, tag_ids)

    def _frontier_cells(self, state: MinerSkillState) -> set[Coord]:
        frontier: set[Coord] = set()
        for cell in state.known_free_cells:
            for _, neighbor in self._neighbors(cell):
                if neighbor not in state.known_free_cells and neighbor not in state.blocked_cells:
                    frontier.add(cell)
                    break
        return frontier

    def _frontier_near(self, state: MinerSkillState, anchors: set[Coord], max_anchor_distance: int) -> set[Coord]:
        frontier = self._frontier_cells(state)
        if not anchors:
            return frontier
        near_frontier: set[Coord] = set()
        for cell in frontier:
            if min(abs(cell[0] - anchor[0]) + abs(cell[1] - anchor[1]) for anchor in anchors) <= max_anchor_distance:
                near_frontier.add(cell)
        return near_frontier or frontier

    def _predicted_extractor_positions(self, state: MinerSkillState) -> set[Coord]:
        predicted: set[Coord] = set()
        hub_set = state.verified_hubs if state.verified_hubs else state.known_hubs
        for hub_row, hub_col in hub_set:
            for d_row, d_col in _HUB_EXTRACTOR_OFFSETS:
                predicted.add((hub_row + d_row, hub_col + d_col))
        return predicted

    def _bfs_first_direction(self, state: MinerSkillState, start: Coord, goal: Coord) -> str | None:
        if start == goal:
            return self._starter._fallback_action_name
        if goal not in state.known_free_cells:
            return None
        avoid = (state.known_hazard_stations | getattr(state, 'contamination_avoid_cells', set())) - {goal, start}
        frontier: deque[Coord] = deque([start])
        parents: dict[Coord, tuple[Coord, str] | None] = {start: None}
        while frontier:
            cell = frontier.popleft()
            if cell == goal:
                break
            for direction, neighbor in self._neighbors(cell):
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

    def _bfs_optimistic_direction(self, state: MinerSkillState, start: Coord, goal: Coord, max_cells: int = 20000) -> str | None:
        """Optimistic BFS: treat unknown cells as traversable, avoid known walls and hazard stations."""
        if start == goal:
            return self._starter._fallback_action_name
        avoid = (state.known_hazard_stations | getattr(state, 'contamination_avoid_cells', set())) - {goal, start}
        frontier: deque[Coord] = deque([start])
        parents: dict[Coord, tuple[Coord, str] | None] = {start: None}
        while frontier and len(parents) < max_cells:
            cell = frontier.popleft()
            if cell == goal:
                break
            for direction, neighbor in self._neighbors(cell):
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

    def _bfs_without_cooldowns(self, state: MinerSkillState, start: Coord, goal: Coord) -> str | None:
        """Fallback BFS ignoring cooldown-blocked cells. Used when cooldowns block all paths."""
        if start == goal:
            return self._starter._fallback_action_name
        cooldown_cells = set(state.move_cooldowns.keys())
        if not cooldown_cells:
            return None
        # Temporarily restore cooldown cells as free
        original_blocked = set(state.blocked_cells)
        original_free = set(state.known_free_cells)
        state.blocked_cells -= cooldown_cells
        state.known_free_cells |= cooldown_cells
        direction = self._bfs_first_direction(state, start, goal)
        state.blocked_cells = original_blocked
        state.known_free_cells = original_free
        return direction

    def _move_to(self, state: MinerSkillState, current_abs: Coord, target_abs: Coord | None) -> tuple[Action, MinerSkillState]:
        if target_abs is None:
            return self._safe_wander(state)
        direction = self._bfs_first_direction(state, current_abs, target_abs)
        if direction is None:
            direction = self._bfs_without_cooldowns(state, current_abs, target_abs)
        if direction is None:
            return self._safe_wander(state)
        return self._starter._action(f"move_{direction}"), state

    def _move_toward_target(
        self,
        state: MinerSkillState,
        current_abs: Coord,
        target_abs: Coord | None,
    ) -> tuple[Action, MinerSkillState]:
        if target_abs is None:
            return self._safe_wander(state)
        direction = self._bfs_first_direction(state, current_abs, target_abs)
        if direction is not None:
            return self._starter._action(f"move_{direction}"), state

        # Issue-44: try BFS ignoring cooldowns before falling through to optimistic BFS
        direction = self._bfs_without_cooldowns(state, current_abs, target_abs)
        if direction is not None:
            return self._starter._action(f"move_{direction}"), state

        # BFS failed (path requires unexplored territory) - try optimistic BFS through unknown cells
        direction = self._bfs_optimistic_direction(state, current_abs, target_abs)
        if direction is not None:
            return self._starter._action(f"move_{direction}"), state

        frontier_cells = self._frontier_cells(state)
        if not frontier_cells:
            return self._safe_wander(state)

        best_frontier = min(
            frontier_cells,
            key=lambda cell: (
                abs(cell[0] - target_abs[0]) + abs(cell[1] - target_abs[1]),
                abs(cell[0] - current_abs[0]) + abs(cell[1] - current_abs[1]),
                cell,
            ),
        )
        if current_abs == best_frontier:
            _contam = getattr(state, 'contamination_avoid_cells', set())
            for direction_name, neighbor in sorted(
                self._neighbors(current_abs),
                key=lambda item: (
                    item[1] in state.blocked_cells,
                    item[1] in state.known_free_cells,
                    item[1] in _contam,
                    abs(item[1][0] - target_abs[0]) + abs(item[1][1] - target_abs[1]),
                ),
            ):
                if neighbor in state.blocked_cells or neighbor in state.known_free_cells:
                    continue
                return self._starter._action(f"move_{direction_name}"), state
            return self._safe_wander(state)
        return self._move_to(state, current_abs, best_frontier)

    def _explore(self, obs: AgentObservation, state: MinerSkillState) -> tuple[Action, MinerSkillState]:
        if state.last_mode != "explore":
            logger.info("agent=%s mode=explore", obs.agent_id)
            state.last_mode = "explore"
        current_abs = self._current_abs(obs)
        frontier_cells = self._frontier_cells(state)
        contam_avoid = getattr(state, 'contamination_avoid_cells', set())
        if current_abs in frontier_cells:
            safe_dir = None
            any_dir = None
            for direction, neighbor in self._neighbors(current_abs):
                if neighbor in state.blocked_cells:
                    continue
                if neighbor not in state.known_free_cells:
                    if any_dir is None:
                        any_dir = direction
                    if neighbor not in contam_avoid and safe_dir is None:
                        safe_dir = direction
            pick = safe_dir if safe_dir is not None else any_dir
            if pick is not None:
                return self._starter._action(f"move_{pick}"), replace(state, last_mode=state.last_mode)
        target_abs = self._nearest_known(current_abs, frontier_cells)
        action, next_state = self._move_to(state, current_abs, target_abs)
        return action, replace(next_state, last_mode=state.last_mode)

    def _explore_near_hub(self, obs: AgentObservation, state: MinerSkillState) -> tuple[Action, MinerSkillState]:
        if state.last_mode != "explore":
            logger.info("agent=%s mode=explore", obs.agent_id)
            state.last_mode = "explore"
        current_abs = self._current_abs(obs)
        frontier_cells = self._frontier_near(state, state.known_hubs, max_anchor_distance=_HUB_SEARCH_DISTANCE)
        if current_abs in frontier_cells:
            ordered = sorted(
                self._neighbors(current_abs),
                key=lambda item: (
                    item[1] in state.blocked_cells,
                    item[1] in state.known_free_cells,
                    min(
                        (abs(item[1][0] - hub[0]) + abs(item[1][1] - hub[1]) for hub in state.known_hubs),
                        default=9999,
                    ),
                ),
            )
            for direction, neighbor in ordered:
                if neighbor in state.blocked_cells or neighbor in state.known_free_cells:
                    continue
                return self._starter._action(f"move_{direction}"), replace(state, last_mode=state.last_mode)
        target_abs = self._nearest_known(current_abs, frontier_cells)
        action, next_state = self._move_to(state, current_abs, target_abs)
        return action, replace(next_state, last_mode=state.last_mode)

    def _select_miner_station(self, current_abs: Coord, state: MinerSkillState) -> Coord | None:
        stations = state.known_miner_stations
        if not stations:
            return None
        if state.gear_contamination_count >= 4 and len(stations) > 1:
            skip = (state.gear_contamination_count - 4) % len(stations)
            sorted_stations = sorted(stations, key=lambda s: abs(s[0] - current_abs[0]) + abs(s[1] - current_abs[1]))
            return sorted_stations[min(skip, len(sorted_stations) - 1)]
        return self._nearest_known(current_abs, stations)

    def _gear_up(self, obs: AgentObservation, state: MinerSkillState) -> tuple[Action, MinerSkillState]:
        if state.last_mode != "gear_up":
            logger.info("agent=%s mode=gear_up", obs.agent_id)
            state.last_mode = "gear_up"
        current_abs = self._current_abs(obs)
        preferred_side = state.gear_up_approach_rotation % 4 if state.gear_contamination_count > 0 else None
        visible_target = self._closest_visible_location(obs, self._miner_station_tags)
        if visible_target is not None:
            target_abs = self._visible_abs_cell(current_abs, visible_target)
            result = self._navigate_to_blocked_target(state, current_abs, target_abs, preferred_side=preferred_side)
            if result is not None:
                action, next_state = result
                return action, replace(next_state, last_mode=state.last_mode)
            action, next_state = self._move_toward_target(state, current_abs, target_abs)
            return action, replace(next_state, last_mode=state.last_mode)
        target_abs = self._select_miner_station(current_abs, state)
        if target_abs is None:
            if state.known_hubs:
                return self._explore_near_hub(obs, state)
            return self._explore(obs, state)
        result = self._navigate_to_blocked_target(state, current_abs, target_abs, preferred_side=preferred_side)
        if result is not None:
            action, next_state = result
            return action, replace(next_state, last_mode=state.last_mode)
        action, next_state = self._move_toward_target(state, current_abs, target_abs)
        return action, replace(next_state, last_mode=state.last_mode)

    def _scarce_element(self, obs: AgentObservation) -> str | None:
        """Issue-16: return the element the agent has least of, or None if balanced."""
        counts = self._inventory_counts(obs)
        if not counts and not any(counts.get(e, 0) for e in ELEMENTS):
            return None
        min_count = min(counts.get(e, 0) for e in ELEMENTS)
        max_count = max(counts.get(e, 0) for e in ELEMENTS)
        # Issue-36 v15: reduced threshold from 5 to 3 for faster individual balancing.
        # With return_load=20, miners carry ~20 resources. A threshold of 5 means a miner
        # mines 5 of one element before seeking diversity; 3 triggers earlier balancing.
        if max_count - min_count < 3:
            return None
        for e in ELEMENTS:
            if counts.get(e, 0) == min_count:
                return e
        return None

    def _team_scarce_element(self) -> str | None:
        """Issue-36 v15: return the element the team has deposited least of.

        Uses SharedMap.total_deposits to identify which element is bottlenecking
        heart crafting. Hearts need 7 of EACH element, so the limiting element
        determines throughput. By routing miners to the team-scarce element,
        we maximize heart crafting rate across the team.
        """
        sm = self._shared_map
        if sm is None or not hasattr(sm, "total_deposits"):
            return None
        deposits = sm.total_deposits
        total = sum(deposits.values())
        # Issue-36 v17: require minimum total deposits (28 = one heart's worth)
        # before activating team coordination. With sparse data, the first deposit
        # creates an artificial imbalance that herds all miners to one element.
        if total < 28:
            return None
        min_val = min(deposits.values())
        max_val = max(deposits.values())
        if max_val - min_val < 5:
            return None
        for elem, val in deposits.items():
            if val == min_val:
                return elem
        return None

    _EXTRACTOR_DEPLETION_THRESHOLD = 40

    def _active_extractors(self, state: MinerSkillState) -> set[Coord]:
        return state.known_extractors - state.depleted_extractors

    def _active_extractors_for_element(self, state: MinerSkillState, element: str) -> set[Coord]:
        return state.extractors_by_element.get(element, set()) - state.depleted_extractors

    def _check_extractor_depletion(self, obs: AgentObservation, state: MinerSkillState) -> None:
        """Mark nearest extractor as depleted if miner hasn't gained resources for too long."""
        current_abs = self._current_abs(obs)
        carried = self._carried_total(obs)

        if state.last_mode == "mine_until_full" and carried == state.last_carried_total:
            state.steps_near_extractor_no_gain += 1
        else:
            state.steps_near_extractor_no_gain = 0

        if state.steps_near_extractor_no_gain >= self._EXTRACTOR_DEPLETION_THRESHOLD:
            active = self._active_extractors(state)
            if active:
                nearest = self._nearest_known(current_abs, active)
                if nearest is not None:
                    dist = abs(nearest[0] - current_abs[0]) + abs(nearest[1] - current_abs[1])
                    if dist <= 3:
                        state.depleted_extractors.add(nearest)
                        logger.info(
                            "agent=%s EXTRACTOR_DEPLETED pos=%s extractor=%s active_remaining=%d",
                            obs.agent_id, current_abs, nearest,
                            len(self._active_extractors(state)),
                        )
            state.steps_near_extractor_no_gain = 0

    def _mine_until_full(self, obs: AgentObservation, state: MinerSkillState) -> tuple[Action, MinerSkillState]:
        if state.last_mode != "mine_until_full":
            logger.info("agent=%s mode=mine_until_full", obs.agent_id)
            state.last_mode = "mine_until_full"
        current_abs = self._current_abs(obs)

        scarce = self._team_scarce_element() or self._scarce_element(obs)
        if scarce and scarce in self._extractor_tags_by_element:
            scarce_tags = self._extractor_tags_by_element[scarce]
            visible_scarce = self._closest_visible_location(obs, scarce_tags)
            if visible_scarce is not None:
                target_abs = self._visible_abs_cell(current_abs, visible_scarce)
                if target_abs not in state.depleted_extractors:
                    result = self._navigate_to_blocked_target(state, current_abs, target_abs)
                    if result is not None:
                        action, next_state = result
                        return action, replace(next_state, last_mode=state.last_mode)
                    action, next_state = self._move_toward_target(state, current_abs, target_abs)
                    return action, replace(next_state, last_mode=state.last_mode)
            scarce_known = self._active_extractors_for_element(state, scarce)
            if scarce_known:
                target_abs = self._nearest_extractor_hub_weighted(current_abs, scarce_known, state)
                if target_abs is not None:
                    result = self._navigate_to_blocked_target(state, current_abs, target_abs)
                    if result is not None:
                        action, next_state = result
                        return action, replace(next_state, last_mode=state.last_mode)
                    action, next_state = self._move_toward_target(state, current_abs, target_abs)
                    return action, replace(next_state, last_mode=state.last_mode)

        visible_target = self._closest_visible_location(obs, self._starter._extractor_tags)
        if visible_target is not None:
            target_abs = self._visible_abs_cell(current_abs, visible_target)
            if target_abs not in state.depleted_extractors:
                result = self._navigate_to_blocked_target(state, current_abs, target_abs)
                if result is not None:
                    action, next_state = result
                    return action, replace(next_state, last_mode=state.last_mode)
                action, next_state = self._move_toward_target(state, current_abs, target_abs)
                return action, replace(next_state, last_mode=state.last_mode)
        active = self._active_extractors(state)
        target_abs = self._nearest_extractor_hub_weighted(current_abs, active, state)
        if target_abs is None:
            if state.known_hubs:
                predicted = self._predicted_extractor_positions(state) - state.depleted_extractors
                predicted_target = self._nearest_extractor_hub_weighted(current_abs, predicted, state)
                if predicted_target is not None:
                    result = self._navigate_to_blocked_target(state, current_abs, predicted_target)
                    if result is not None:
                        action, next_state = result
                        return action, replace(next_state, last_mode=state.last_mode)
                    action, next_state = self._move_toward_target(state, current_abs, predicted_target)
                    return action, replace(next_state, last_mode=state.last_mode)
                return self._explore_near_hub(obs, state)
            return self._explore(obs, state)
        result = self._navigate_to_blocked_target(state, current_abs, target_abs)
        if result is not None:
            action, next_state = result
            return action, replace(next_state, last_mode=state.last_mode)
        action, next_state = self._move_toward_target(state, current_abs, target_abs)
        return action, replace(next_state, last_mode=state.last_mode)

    _APPROACH_SIDES = (("north", (-1, 0)), ("east", (0, 1)), ("south", (1, 0)), ("west", (0, -1)))

    def _navigate_to_blocked_target(
        self, state: MinerSkillState, current_abs: Coord, blocked_target: Coord,
        preferred_side: int | None = None,
    ) -> tuple[Action, MinerSkillState] | None:
        """Navigate toward a blocked object (hub/station) via its best adjacent approach cell.

        Issue-16 fix: hubs are blocked objects. BFS to them fails because they're
        not in known_free_cells. Navigate to the nearest adjacent free cell instead,
        then step into the blocked cell to trigger the interaction handler.
        """
        # Find adjacent cells that aren't blocked
        approach_candidates = []
        for i, (_, (dr, dc)) in enumerate(self._APPROACH_SIDES):
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
            approach = approach_candidates[0][1]
        else:
            approach = min((c for _, c in approach_candidates), key=lambda c: abs(c[0] - current_abs[0]) + abs(c[1] - current_abs[1]))
        if current_abs == approach:
            # Already adjacent — step into the blocked target
            dr = blocked_target[0] - current_abs[0]
            dc = blocked_target[1] - current_abs[1]
            if abs(dr) >= abs(dc):
                direction = "south" if dr > 0 else "north"
            else:
                direction = "east" if dc > 0 else "west"
            return self._starter._action(f"move_{direction}"), state
        # Navigate to approach cell
        direction = self._bfs_first_direction(state, current_abs, approach)
        if direction is not None:
            return self._starter._action(f"move_{direction}"), state
        direction = self._bfs_without_cooldowns(state, current_abs, approach)
        if direction is not None:
            return self._starter._action(f"move_{direction}"), state
        direction = self._bfs_optimistic_direction(state, current_abs, approach)
        if direction is not None:
            return self._starter._action(f"move_{direction}"), state
        return None

    def _greedy_walk_toward(self, current_abs: Coord, target_abs: Coord) -> Action:
        dr = target_abs[0] - current_abs[0]
        dc = target_abs[1] - current_abs[1]
        if dr == 0 and dc == 0:
            return self._starter._action("noop")
        if abs(dr) >= abs(dc):
            return self._starter._action("move_south" if dr > 0 else "move_north")
        return self._starter._action("move_east" if dc > 0 else "move_west")

    def _greedy_walk_toward_safe(self, state: MinerSkillState, current_abs: Coord, target_abs: Coord) -> Action:
        avoid = state.known_hazard_stations | state.blocked_cells | getattr(state, 'contamination_avoid_cells', set())
        candidates = []
        for dir_name, (ddr, ddc) in _DIRECTION_DELTAS:
            neighbor = (current_abs[0] + ddr, current_abs[1] + ddc)
            dist = abs(neighbor[0] - target_abs[0]) + abs(neighbor[1] - target_abs[1])
            hazard = neighbor in avoid
            candidates.append((hazard, dist, dir_name))
        candidates.sort()
        return self._starter._action(f"move_{candidates[0][2]}")

    def _hub_preferred_side(self, obs: AgentObservation, state: MinerSkillState) -> int:
        return (obs.agent_id + state.hub_approach_rotation) % 4

    def _nearest_deposit_target(self, current_abs: Coord, state: MinerSkillState) -> Coord | None:
        hub_candidates = state.verified_hubs if state.verified_hubs else state.known_hubs
        hub_target = self._nearest_known(current_abs, hub_candidates)
        if hub_target is None:
            return None
        hub_dist = abs(current_abs[0] - hub_target[0]) + abs(current_abs[1] - hub_target[1])
        sm = self._shared_map
        if sm is not None and hasattr(sm, 'known_friendly_junctions') and sm.known_friendly_junctions:
            best_junc = None
            best_dist = hub_dist
            for junc in sm.known_friendly_junctions:
                jdist = abs(current_abs[0] - junc[0]) + abs(current_abs[1] - junc[1])
                if jdist < best_dist - 5:
                    best_dist = jdist
                    best_junc = junc
            if best_junc is not None:
                return best_junc
        return hub_target

    def _deposit_to_hub(self, obs: AgentObservation, state: MinerSkillState) -> tuple[Action, MinerSkillState]:
        if state.last_mode != "deposit_to_hub":
            logger.info("agent=%s mode=deposit_to_hub load=%s", obs.agent_id, self._carried_total(obs))
            state.last_mode = "deposit_to_hub"
        current_abs = self._current_abs(obs)
        preferred_side = self._hub_preferred_side(obs, state)
        visible_target = self._closest_visible_location(obs, self._hub_tags)
        if visible_target is not None:
            target_abs = self._visible_abs_cell(current_abs, visible_target)
            result = self._navigate_to_blocked_target(state, current_abs, target_abs, preferred_side=preferred_side)
            if result is not None:
                action, next_state = result
                return action, replace(next_state, last_mode=state.last_mode)
            return self._greedy_walk_toward_safe(state, current_abs, target_abs), state
        target_abs = self._nearest_deposit_target(current_abs, state)
        if target_abs is None:
            hub_candidates = state.verified_hubs if state.verified_hubs else state.known_hubs
            target_abs = self._nearest_known(current_abs, hub_candidates)
        if target_abs is None and state.remembered_hub_row_from_spawn is not None and state.remembered_hub_col_from_spawn is not None:
            target_abs = (state.remembered_hub_row_from_spawn, state.remembered_hub_col_from_spawn)
            state.known_hubs.add(target_abs)
            state.blocked_cells.add(target_abs)
        if target_abs is None:
            return self._explore(obs, state)
        result = self._navigate_to_blocked_target(state, current_abs, target_abs, preferred_side=preferred_side)
        if result is not None:
            action, next_state = result
            return action, replace(next_state, last_mode=state.last_mode)
        return self._greedy_walk_toward_safe(state, current_abs, target_abs), state

    _MINER_HP_RETREAT_THRESHOLD = 0.65

    def _read_hp(self, obs: AgentObservation) -> int | None:
        center = self._starter._center
        for token in obs.tokens:
            if token.location != center:
                continue
            if token.feature.name == "inv:hp":
                return int(token.value)
        return None

    def _read_all_inv(self, obs: AgentObservation) -> dict[str, int]:
        center = self._starter._center
        inv: dict[str, int] = {}
        for token in obs.tokens:
            if token.location != center:
                continue
            name = token.feature.name
            if name.startswith("inv:"):
                inv[name] = int(token.value)
        return inv

    def _check_miner_hp(self, obs: AgentObservation, state: MinerSkillState) -> bool:
        hp = self._read_hp(obs)
        if hp is None:
            state.retreating_to_hub = False
            return False
        if hp > state.max_hp_seen:
            state.max_hp_seen = hp
        if state.max_hp_seen <= 0:
            return False
        hp_fraction = hp / state.max_hp_seen
        late = self._shared_map is not None and self._shared_map.late_game
        retreat_threshold = 0.75 if late else self._MINER_HP_RETREAT_THRESHOLD
        if hp_fraction < retreat_threshold and not state.retreating_to_hub:
            inv = self._read_all_inv(obs)
            logger.info("agent=%s MINER_HP_LOW hp=%d/%d (%.0f%%) inv=%s retreating to hub",
                        obs.agent_id, hp, state.max_hp_seen, hp_fraction * 100, inv)
            state.retreating_to_hub = True
        elif state.retreating_to_hub and hp_fraction >= (0.90 if late else 0.85):
            logger.info("agent=%s MINER_HP_OK hp=%d/%d resuming mining",
                        obs.agent_id, hp, state.max_hp_seen)
            state.retreating_to_hub = False
        return state.retreating_to_hub

    def _nearest_extractor_to_hub(self, state: MinerSkillState) -> Coord | None:
        hub_set = state.verified_hubs if state.verified_hubs else state.known_hubs
        extractors = state.verified_extractors if state.verified_extractors else state.known_extractors
        if not hub_set or not state.known_extractors:
            return None
        hub = min(hub_set, key=lambda h: abs(h[0]) + abs(h[1]))
        return min(
            state.known_extractors,
            key=lambda e: abs(e[0] - hub[0]) + abs(e[1] - hub[1]),
        )

    def _nearest_scarce_extractor_to_hub(self, state: MinerSkillState, obs: AgentObservation) -> Coord | None:
        hub_set = state.verified_hubs if state.verified_hubs else state.known_hubs
        if not hub_set:
            return None
        hub = min(hub_set, key=lambda h: abs(h[0]) + abs(h[1]))
        scarce = self._team_scarce_element() or self._scarce_element(obs)
        if scarce:
            candidates = state.extractors_by_element.get(scarce, set())
            if candidates:
                return min(candidates, key=lambda e: abs(e[0] - hub[0]) + abs(e[1] - hub[1]))
        if state.known_extractors:
            return min(
                state.known_extractors,
                key=lambda e: abs(e[0] - hub[0]) + abs(e[1] - hub[1]),
            )
        return None

    _step_counter: dict[int, int] = {}

    _STUCK_THRESHOLD = 150
    _STUCK_EXPLORE_STEPS = 60

    def step_with_state(self, obs: AgentObservation, state: MinerSkillState) -> tuple[Action, MinerSkillState]:
        self._update_map_memory(obs, state)

        agent_id = obs.agent_id
        self._step_counter[agent_id] = self._step_counter.get(agent_id, 0) + 1
        step_num = self._step_counter[agent_id]

        hp = self._read_hp(obs)
        if hp is not None:
            if hp > state.max_hp_seen:
                state.max_hp_seen = hp
            _late = self._shared_map is not None and self._shared_map.late_game
            _miner_thr = 0.75 if _late else self._MINER_HP_RETREAT_THRESHOLD
            if state.max_hp_seen > 0 and hp < state.max_hp_seen * _miner_thr:
                if not state.retreating_to_hub:
                    logger.info("agent=%s MINER_HP_LOW hp=%d/%d retreating",
                                obs.agent_id, hp, state.max_hp_seen)
                    state.retreating_to_hub = True
                action, state = self._deposit_to_hub(obs, state)
                self._record_move_target(action, obs, state)
                return action, state
            elif state.retreating_to_hub and hp >= state.max_hp_seen * 0.5:
                state.retreating_to_hub = False

        gear = self._starter._current_gear(self._starter._inventory_items(obs))
        if gear != "miner":
            state.steps_in_current_mode = 0
            action, state = self._gear_up(obs, state)
            self._record_move_target(action, obs, state)
            return action, state

        carried = self._carried_total(obs)

        if carried != state.last_carried_total:
            state.steps_in_current_mode = 0
            state.last_carried_total = carried

        # Issue-44: detect depleted extractors
        self._check_extractor_depletion(obs, state)

        if state.stuck_explore_remaining > 0:
            state.stuck_explore_remaining -= 1
            if state.stuck_explore_remaining == 0:
                logger.info("agent=%s stuck_explore done, resuming normal mode", agent_id)
            action, state = self._explore(obs, state)
            self._record_move_target(action, obs, state)
            return action, state

        state.steps_in_current_mode += 1

        if state.steps_in_current_mode > self._STUCK_THRESHOLD:
            current_abs = self._current_abs(obs)
            active = self._active_extractors(state)
            hub_dist = "?"
            if state.known_hubs:
                nearest_hub = min(state.known_hubs, key=lambda h: abs(h[0] - current_abs[0]) + abs(h[1] - current_abs[1]))
                hub_dist = abs(nearest_hub[0] - current_abs[0]) + abs(nearest_hub[1] - current_abs[1])

            # Issue-44: if stuck while trying to mine (carried unchanged), the
            # nearest extractor is likely depleted. Mark it so the miner avoids it.
            if state.last_mode in ("mine_until_full", "explore") and active:
                nearest_ext = self._nearest_known(current_abs, active)
                if nearest_ext is not None:
                    state.depleted_extractors.add(nearest_ext)
                    active = self._active_extractors(state)
                    logger.info(
                        "agent=%s EXTRACTOR_DEPLETED_BY_STUCK extractor=%s active_remaining=%d depleted_total=%d",
                        agent_id, nearest_ext, len(active), len(state.depleted_extractors),
                    )

            if state.last_mode == "deposit_to_hub":
                state.hub_approach_rotation = (state.hub_approach_rotation + 1) % 4
            logger.info(
                "agent=%s STUCK step=%d mode=%s steps_in_mode=%d pos=%s hub_dist=%s carried=%d active_extractors=%d depleted=%d",
                agent_id, step_num, state.last_mode, state.steps_in_current_mode,
                current_abs, hub_dist, carried, len(active), len(state.depleted_extractors),
            )
            state.steps_in_current_mode = 0
            if not active:
                if state.depleted_extractors:
                    logger.info(
                        "agent=%s RESET_DEPLETED: all %d extractors depleted, resetting for retry",
                        agent_id, len(state.depleted_extractors),
                    )
                    state.depleted_extractors.clear()
                state.stuck_explore_remaining = self._STUCK_EXPLORE_STEPS * 3
            else:
                state.stuck_explore_remaining = self._STUCK_EXPLORE_STEPS
            action, state = self._explore(obs, state)
            self._record_move_target(action, obs, state)
            return action, state

        if carried >= self._return_load:
            action, state = self._deposit_to_hub(obs, state)
            self._record_move_target(action, obs, state)
            return action, state

        action, state = self._mine_until_full(obs, state)
        self._record_move_target(action, obs, state)
        return action, state

    def _record_move_target(self, action: Action, obs: AgentObservation, state: MinerSkillState) -> None:
        """Record the move target so the cooldown system can detect failures next step."""
        action_name = action.name if hasattr(action, "name") else ""
        if action_name.startswith("move_"):
            current_abs = self._current_abs(obs)
            direction = action_name[len("move_"):]
            state.last_move_target = self._move_target(current_abs, direction)
