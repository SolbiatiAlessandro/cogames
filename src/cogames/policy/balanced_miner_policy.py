"""Balanced miner policy for issue #24: element-aware mining to optimize make_heart cycle.

The hub needs 7 of each of 4 elements (28 total) to craft a heart via make_heart.
The default miner targets the closest extractor, causing heavy element skew
(e.g., 30 oxygen + 1 germanium = 0 hearts crafted).

This policy tracks element counts in inventory and targets the rarest element's
extractor so each deposit trip carries a balanced load.

Key design decisions:
- Always deposit when load is full (return_load items), regardless of balance
- Target the deficit element by preference when exploring for extractors
- If target element extractor not found, fall back to any extractor
  (ensures deposits happen, even if somewhat unbalanced)
- On deposit, reset element targets so next trip re-balances
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field, replace

from cogames.policy.aligner_agent import AlignerPolicyImpl, AlignerState, SharedMap
from cogames.policy.llm_skills import MinerSkillImpl, MinerSkillState
from cogames.policy.starter_agent import ELEMENTS
from mettagrid.policy.policy import MultiAgentPolicy, StatefulAgentPolicy, StatefulPolicyImpl
from mettagrid.policy.policy_env_interface import PolicyEnvInterface
from mettagrid.simulator import Action
from mettagrid.simulator.interface import AgentObservation

logger = logging.getLogger("cogames.policy.balanced_miner")

_DIRECTION_DELTAS = [("north", (-1, 0)), ("south", (1, 0)), ("east", (0, 1)), ("west", (0, -1))]

Coord = tuple[int, int]

# How many of each element to target per trip before depositing
_BALANCED_TARGET_PER_ELEMENT = 7
_ELEMENTS_LIST = list(ELEMENTS)  # ["carbon", "oxygen", "germanium", "silicon"]
# Default return load: 4 elements * 7 each = 28
_DEFAULT_RETURN_LOAD = 28


@dataclass
class BalancedMinerState(MinerSkillState):
    """Extended miner state that tracks per-element extractor locations."""
    # Per-element known extractor positions
    known_carbon_extractors: set[Coord] = field(default_factory=set)
    known_oxygen_extractors: set[Coord] = field(default_factory=set)
    known_germanium_extractors: set[Coord] = field(default_factory=set)
    known_silicon_extractors: set[Coord] = field(default_factory=set)
    # Current target element (changes when balanced enough)
    current_target_element: str | None = None
    # Steps spent looking for target element without finding it
    target_search_steps: int = 0


class BalancedMinerPolicyImpl(MinerSkillImpl, StatefulPolicyImpl[BalancedMinerState]):
    """Miner that targets the deficit element to produce balanced deposits for make_heart.

    Strategy:
    1. Compute which element we have least of in cargo
    2. Navigate to extractor of that type
    3. If known extractor of that type: go there
    4. If not known after _SEARCH_TIMEOUT steps: fall back to any extractor
    5. Deposit when load is full OR when carrying balanced 7+7+7+7
    """

    # Steps to search for target element before falling back to any extractor
    _SEARCH_TIMEOUT = 80

    def __init__(
        self,
        policy_env_info: PolicyEnvInterface,
        agent_id: int,
        return_load: int = _DEFAULT_RETURN_LOAD,
        shared_map=None,
    ) -> None:
        super().__init__(policy_env_info, agent_id, return_load=return_load, shared_map=shared_map)
        # Per-element extractor tag sets
        self._element_extractor_tags: dict[str, set[int]] = {}
        for elem in _ELEMENTS_LIST:
            self._element_extractor_tags[elem] = self._starter._resolve_tag_ids([f"{elem}_extractor"])
        logger.info("agent=%s BalancedMinerPolicyImpl initialized return_load=%d element_tags=%s",
                    agent_id, return_load, {e: len(t) for e, t in self._element_extractor_tags.items()})

    def initial_agent_state(self) -> BalancedMinerState:
        base = super().initial_agent_state()
        state = BalancedMinerState(
            wander_direction_index=base.wander_direction_index,
            wander_steps_remaining=base.wander_steps_remaining,
            last_mode=base.last_mode,
            remembered_hub_row_from_spawn=base.remembered_hub_row_from_spawn,
            remembered_hub_col_from_spawn=base.remembered_hub_col_from_spawn,
        )
        self._bind_shared_map_miner(state)
        return state

    def _copy_balanced_with(self, state: BalancedMinerState, base: MinerSkillState) -> BalancedMinerState:
        sm = self._shared_map
        return replace(
            state,
            wander_direction_index=base.wander_direction_index,
            wander_steps_remaining=base.wander_steps_remaining,
            last_mode=base.last_mode,
            remembered_hub_row_from_spawn=base.remembered_hub_row_from_spawn,
            remembered_hub_col_from_spawn=base.remembered_hub_col_from_spawn,
            known_free_cells=sm.known_free_cells if sm else set(base.known_free_cells),
            blocked_cells=sm.blocked_cells if sm else set(base.blocked_cells),
            known_hubs=sm.known_hubs if sm else set(base.known_hubs),
            known_miner_stations=sm.known_miner_stations if sm else set(base.known_miner_stations),
            known_extractors=sm.known_extractors if sm else set(base.known_extractors),
            known_hazard_stations=sm.known_hazard_stations if sm else set(base.known_hazard_stations),
            last_pos=base.last_pos,
            last_move_target=base.last_move_target,
            # Preserve balanced miner specific fields
            known_carbon_extractors=state.known_carbon_extractors,
            known_oxygen_extractors=state.known_oxygen_extractors,
            known_germanium_extractors=state.known_germanium_extractors,
            known_silicon_extractors=state.known_silicon_extractors,
            current_target_element=state.current_target_element,
            target_search_steps=state.target_search_steps,
        )

    def _update_element_extractors(self, obs: AgentObservation, state: BalancedMinerState) -> None:
        """Track per-element extractor positions from observation tokens."""
        current_abs = self._current_abs(obs)
        for token in obs.tokens:
            if token.feature.name != "tag" or token.location is None:
                continue
            for elem in _ELEMENTS_LIST:
                tag_ids = self._element_extractor_tags[elem]
                if token.value in tag_ids:
                    abs_cell = self._visible_abs_cell(current_abs, token.location)
                    elem_set = getattr(state, f"known_{elem}_extractors")
                    elem_set.add(abs_cell)

    def _best_approach_cell(self, state: BalancedMinerState, current_abs: Coord, blocked_target: Coord) -> Coord | None:
        """Find the best adjacent free cell for approaching a blocked target (e.g., hub)."""
        candidates = [
            (blocked_target[0] + dr, blocked_target[1] + dc)
            for _, (dr, dc) in _DIRECTION_DELTAS
            if (blocked_target[0] + dr, blocked_target[1] + dc) not in state.blocked_cells
        ]
        if not candidates:
            return None
        return min(candidates, key=lambda c: abs(c[0] - current_abs[0]) + abs(c[1] - current_abs[1]))

    def _deposit_to_hub(self, obs: AgentObservation, state: BalancedMinerState) -> tuple[Action, BalancedMinerState]:
        """Navigate to hub and deposit. Uses approach-cell strategy (hub is blocked object)."""
        if state.last_mode != "deposit_to_hub":
            logger.info("agent=%s mode=deposit_to_hub load=%d counts=%s",
                        obs.agent_id, self._carried_total(obs), self._inventory_counts(obs))
            state.last_mode = "deposit_to_hub"

        current_abs = self._current_abs(obs)

        # Find hub target: visible first, then known, then remembered spawn position
        hub_abs: Coord | None = None
        visible_target = self._closest_visible_location(obs, self._hub_tags)
        if visible_target is not None:
            hub_abs = self._visible_abs_cell(current_abs, visible_target)
            state.known_hubs.add(hub_abs)
        elif state.known_hubs:
            hub_abs = self._nearest_known(current_abs, state.known_hubs)
        elif (state.remembered_hub_row_from_spawn is not None
              and state.remembered_hub_col_from_spawn is not None):
            hub_abs = (state.remembered_hub_row_from_spawn, state.remembered_hub_col_from_spawn)

        if hub_abs is None:
            # Hub unknown: explore to find it
            action, base_state = self._explore(obs, state)
            return action, self._copy_balanced_with(state, base_state)

        # Find best approach cell (adjacent to hub, not in blocked_cells)
        approach = self._best_approach_cell(state, current_abs, hub_abs)
        if approach is None:
            # All adjacent cells blocked - try greedy move toward hub
            dr = hub_abs[0] - current_abs[0]
            dc = hub_abs[1] - current_abs[1]
            if abs(dr) >= abs(dc):
                direction = "south" if dr > 0 else "north"
            else:
                direction = "east" if dc > 0 else "west"
            return self._starter._action(f"move_{direction}"), state

        if current_abs == approach:
            # Already adjacent to hub: move directly INTO it to trigger deposit
            dr = hub_abs[0] - current_abs[0]
            dc = hub_abs[1] - current_abs[1]
            if abs(dr) >= abs(dc):
                direction = "south" if dr > 0 else "north"
            else:
                direction = "east" if dc > 0 else "west"
            logger.debug("agent=%s depositing_into_hub direction=%s", obs.agent_id, direction)
            return self._starter._action(f"move_{direction}"), state

        # Navigate to approach cell via BFS
        action, base_state = self._move_toward_target(state, current_abs, approach)
        return action, self._copy_balanced_with(state, base_state)

    def _mine_balanced(self, obs: AgentObservation, state: BalancedMinerState) -> tuple[Action, BalancedMinerState]:
        """Mine targeting the deficit element type for balanced deposits.

        Prefers the element we have least of, but falls back to any extractor
        after _SEARCH_TIMEOUT steps to ensure deposits still happen.
        """
        if state.last_mode != "mine_balanced":
            logger.info("agent=%s mode=mine_balanced", obs.agent_id)
            state.last_mode = "mine_balanced"

        counts = self._inventory_counts(obs)
        current_abs = self._current_abs(obs)

        # Update target element: switch when current target is satisfied
        if (state.current_target_element is None
                or counts.get(state.current_target_element, 0) >= _BALANCED_TARGET_PER_ELEMENT):
            deficit_elem = min(_ELEMENTS_LIST, key=lambda e: counts.get(e, 0))
            state.current_target_element = deficit_elem
            state.target_search_steps = 0
            logger.info("agent=%s target_element=%s counts=%s", obs.agent_id, deficit_elem, counts)

        target_elem = state.current_target_element
        elem_extractors = getattr(state, f"known_{target_elem}_extractors")

        # Check if visible extractor of target type
        visible_target = self._closest_visible_location(obs, self._element_extractor_tags[target_elem])
        if visible_target is not None:
            target_abs = self._visible_abs_cell(current_abs, visible_target)
            elem_extractors.add(target_abs)
            state.target_search_steps = 0
            action, base_state = self._move_toward_target(state, current_abs, target_abs)
            return action, self._copy_balanced_with(replace(state, last_mode="mine_balanced"), base_state)

        # Navigate to known extractor of target type
        if elem_extractors:
            target_abs = self._nearest_known(current_abs, elem_extractors)
            if target_abs is not None:
                state.target_search_steps = 0
                action, base_state = self._move_toward_target(state, current_abs, target_abs)
                return action, self._copy_balanced_with(replace(state, last_mode="mine_balanced"), base_state)

        # No known extractor of target type - increment search counter
        state.target_search_steps += 1

        if state.target_search_steps <= self._SEARCH_TIMEOUT:
            # Explore full map to find target element type
            logger.debug("agent=%s searching_for_%s step=%d", obs.agent_id, target_elem, state.target_search_steps)
            action, base_state = self._explore(obs, state)
            return action, self._copy_balanced_with(state, base_state)
        else:
            # Timeout: fall back to any extractor to ensure deposits happen
            logger.info("agent=%s search_timeout_%s falling_back_to_any search_steps=%d",
                        obs.agent_id, target_elem, state.target_search_steps)
            state.target_search_steps = 0
            # Let current_target_element stay as-is so we know what to look for
            action, base_state = self._mine_until_full(obs, state)
            return action, self._copy_balanced_with(state, base_state)

    def _should_deposit_balanced(self, obs: AgentObservation) -> bool:
        """Return True if we have enough of all elements to make a heart (7 of each)."""
        counts = self._inventory_counts(obs)
        if not counts:
            return False
        min_count = min(counts.get(e, 0) for e in _ELEMENTS_LIST)
        return min_count >= _BALANCED_TARGET_PER_ELEMENT

    def step_with_state(self, obs: AgentObservation, state: BalancedMinerState) -> tuple[Action, BalancedMinerState]:
        self._update_map_memory(obs, state)
        self._update_element_extractors(obs, state)

        gear = self._starter._current_gear(self._starter._inventory_items(obs))
        if gear != "miner":
            action, base_state = self._gear_up(obs, state)
            next_state = self._copy_balanced_with(state, base_state)
        elif self._should_deposit_balanced(obs):
            # Balanced load ready: deposit now to craft a heart
            action, next_state = self._deposit_to_hub(obs, state)
            if self._carried_total(obs) == 0:
                # Deposit completed, reset targets
                next_state.current_target_element = None
                next_state.target_search_steps = 0
        elif self._carried_total(obs) >= self._return_load:
            # Full load: deposit regardless of balance (fallback)
            action, next_state = self._deposit_to_hub(obs, state)
        else:
            # Mine targeting deficit element
            action, next_state = self._mine_balanced(obs, state)

        # Track last move target for move-failure feedback (critical for unstuck logic)
        action_name = action.name if hasattr(action, "name") else ""
        if action_name.startswith("move_"):
            current_abs = self._current_abs(obs)
            direction = action_name[len("move_"):]
            next_state.last_move_target = self._move_target(current_abs, direction)

        return action, next_state


class MachinaBalancedRolesPolicy(MultiAgentPolicy):
    """2 LLM-free aligners + 1 balanced miner for issue #24 experiments.

    Uses scripted AlignerPolicyImpl for aligners and BalancedMinerPolicyImpl
    for the miner. No LLM required.
    """
    short_names = ["machina_balanced_roles"]

    def __init__(
        self,
        policy_env_info: PolicyEnvInterface,
        device: str = "cpu",
        num_aligners: int | str = 2,
        aligner_ids: str = "",
        return_load: int | str = _DEFAULT_RETURN_LOAD,
    ):
        super().__init__(policy_env_info, device=device)
        self._return_load = int(return_load)
        self._shared_map = SharedMap()
        n_agents = policy_env_info.num_agents

        # Resolve aligner IDs
        parsed_aligner_ids = tuple(int(p.strip()) for p in aligner_ids.split(",") if p.strip())
        if parsed_aligner_ids:
            self._aligner_ids = frozenset(parsed_aligner_ids)
        else:
            self._aligner_ids = frozenset(range(min(int(num_aligners), n_agents)))

        self._agent_policies: dict[int, StatefulAgentPolicy] = {}

    def agent_policy(self, agent_id: int) -> StatefulAgentPolicy:
        if agent_id not in self._agent_policies:
            if agent_id in self._aligner_ids:
                impl = AlignerPolicyImpl(
                    self._policy_env_info,
                    agent_id,
                    shared_map=self._shared_map,
                )
            else:
                impl = BalancedMinerPolicyImpl(
                    self._policy_env_info,
                    agent_id,
                    return_load=self._return_load,
                    shared_map=self._shared_map,
                )
            self._agent_policies[agent_id] = StatefulAgentPolicy(
                impl,
                self._policy_env_info,
                agent_id=agent_id,
            )
        return self._agent_policies[agent_id]
