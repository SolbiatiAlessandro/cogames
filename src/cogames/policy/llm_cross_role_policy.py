"""Cross-role LLM policy: agents dynamically switch between miner and aligner roles.

Instead of fixed role assignment, each agent asks "what does the team need?" and
can choose to gear up as miner, mine resources, deposit, then switch to aligner
to capture junctions — or stay as aligner throughout if junctions need holding.
"""
from __future__ import annotations

import logging
import re
import json
import time
from dataclasses import dataclass, field, replace
from typing import Callable

from cogames.policy.aligner_agent import (
    AlignerPolicyImpl, AlignerState, SharedMap,
    _FRIENDLY_TERRITORY_DISTANCE, _HP_RETREAT_THRESHOLD,
)
from cogames.policy.llm_cross_role_prompt import (
    CROSS_ROLE_SKILL_DESCRIPTIONS,
    build_cross_role_prompt,
)
from cogames.policy.llm_miner_policy import LLMMinerPlannerClient
from mettagrid.policy.policy import MultiAgentPolicy, StatefulAgentPolicy, StatefulPolicyImpl
from mettagrid.policy.policy_env_interface import PolicyEnvInterface
from mettagrid.simulator import Action
from mettagrid.simulator.interface import AgentObservation

logger = logging.getLogger("cogames.policy.llm_cross_role")

_RETURN_LOAD = 40  # default cargo threshold for depositing


def _parse_cross_role_skill(text: str, valid_skills: set[str]) -> tuple[str | None, str]:
    text = text.strip()
    if not text:
        return None, "empty response"
    fence_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fence_match:
        text = fence_match.group(1).strip()
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        skill = text.splitlines()[0].strip()
        return (skill if skill in valid_skills else None, "non-json response")
    if not isinstance(payload, dict):
        return None, "response was not a JSON object"
    skill = payload.get("skill")
    reason = payload.get("reason", "")
    if not isinstance(skill, str):
        return None, "missing skill field"
    # Normalize common typos/aliases
    aliases = {
        "unstick": "unstuck",
        "align_neutral": "align_junction",
        "align": "align_junction",
        "mine": "mine_resources",
        "deposit": "deposit_resources",
        "gear_up": "gear_up_miner",  # default gear_up → miner
    }
    skill = aliases.get(skill, skill)
    return (skill if skill in valid_skills else None, str(reason))


@dataclass
class CrossRoleState(AlignerState):
    """Merged state for cross-role agents (miner + aligner capabilities)."""
    # Miner-specific map state
    known_miner_stations: set[tuple[int, int]] = field(default_factory=set)
    known_extractors: set[tuple[int, int]] = field(default_factory=set)
    remembered_hub_row: int | None = None
    remembered_hub_col: int | None = None
    # LLM planner state (mirrors LLMAlignerState)
    current_skill: str | None = None
    current_reason: str = ""
    skill_steps: int = 0
    no_move_steps: int = 0
    no_progress_on_target_steps: int = 0
    last_has_heart: bool = False
    last_friendly_junctions: int = 0
    consecutive_unstuck: int = 0
    explore_start_junctions: int = 0
    align_junction_timeouts: int = 0
    get_heart_timeouts: int = 0
    recent_events: list[str] = field(default_factory=list)
    # HP monitoring
    max_hp_seen: int = 0
    retreating: bool = False
    # Resource tracking
    last_carried_total: int = 0


class LLMCrossRolePolicyImpl(AlignerPolicyImpl, StatefulPolicyImpl[CrossRoleState]):
    """Cross-role agent: can mine resources AND align junctions, switching as needed."""

    _UNSTUCK_DIRECTIONS = ("north", "east", "south", "west")

    def __init__(
        self,
        policy_env_info: PolicyEnvInterface,
        agent_id: int,
        planner: LLMMinerPlannerClient,
        shared_map: SharedMap,
        return_load: int = _RETURN_LOAD,
        stuck_threshold: int = 20,
        unstuck_horizon: int = 4,
        total_agents: int = 8,
    ) -> None:
        super().__init__(policy_env_info, agent_id, shared_map=shared_map)
        self._planner = planner
        self._return_load = return_load
        self._stuck_threshold = stuck_threshold
        self._unstuck_horizon = unstuck_horizon
        self._total_agents = total_agents
        self._agent_id = agent_id

        # Resolve miner station tags (similar to MinerSkillImpl)
        miner_station_names = self._miner_station_names(policy_env_info)
        self._miner_station_tags = self._starter._resolve_tag_ids(miner_station_names)

    def _miner_station_names(self, policy_env_info: PolicyEnvInterface) -> list[str]:
        names = {"miner_station"}
        for tag_name in policy_env_info.tags:
            if not tag_name.startswith("type:"):
                continue
            object_name = tag_name.removeprefix("type:")
            if object_name.endswith(":miner") or object_name == "miner":
                names.add(object_name)
        return sorted(names)

    def initial_agent_state(self) -> CrossRoleState:
        base = super().initial_agent_state()
        state = CrossRoleState(
            wander_direction_index=base.wander_direction_index,
            wander_steps_remaining=base.wander_steps_remaining,
            last_mode=base.last_mode,
        )
        self._bind_shared_map(state)
        # Also bind miner-specific shared map fields
        if self._shared_map:
            state.known_miner_stations = self._shared_map.known_miner_stations
            state.known_extractors = self._shared_map.known_extractors
        return state

    def _copy_with(self, state: CrossRoleState, base: AlignerState) -> CrossRoleState:
        sm = self._shared_map
        return replace(
            state,
            wander_direction_index=base.wander_direction_index,
            wander_steps_remaining=base.wander_steps_remaining,
            last_mode=base.last_mode,
            known_free_cells=sm.known_free_cells if sm else set(base.known_free_cells),
            blocked_cells=sm.blocked_cells if sm else set(base.blocked_cells),
            move_blocked_cells=sm.move_blocked_cells if sm else set(base.move_blocked_cells),
            known_hubs=sm.known_hubs if sm else set(base.known_hubs),
            known_aligner_stations=sm.known_aligner_stations if sm else set(base.known_aligner_stations),
            known_miner_stations=sm.known_miner_stations if sm else set(state.known_miner_stations),
            known_extractors=sm.known_extractors if sm else set(state.known_extractors),
            known_neutral_junctions=sm.known_neutral_junctions if sm else set(base.known_neutral_junctions),
            known_friendly_junctions=sm.known_friendly_junctions if sm else set(base.known_friendly_junctions),
            known_enemy_junctions=sm.known_enemy_junctions if sm else set(base.known_enemy_junctions),
            known_hazard_stations=sm.known_hazard_stations if sm else set(base.known_hazard_stations),
        )

    def _event(self, state: CrossRoleState, message: str) -> None:
        state.recent_events.append(message)
        del state.recent_events[:-10]

    def _update_map_memory_cross_role(self, obs: AgentObservation, state: CrossRoleState) -> tuple[int, int]:
        """Extended map memory update that also tracks miner stations and extractors."""
        current_abs = self._update_map_memory(obs, state)

        # Also scan for miner stations and extractors
        miner_stations_now: set[tuple[int, int]] = set()
        extractors_now: set[tuple[int, int]] = set()

        for token in obs.tokens:
            if token.feature.name != "tag" or token.location is None:
                continue
            abs_cell = self._visible_abs_cell(current_abs, token.location)
            if token.value in self._miner_station_tags:
                miner_stations_now.add(abs_cell)
            if token.value in self._starter._extractor_tags:
                extractors_now.add(abs_cell)

        state.known_miner_stations.update(miner_stations_now)
        state.known_extractors.update(extractors_now)

        # Update hub memory (remembered position from spawn)
        if state.known_hubs:
            hub = min(state.known_hubs, key=lambda c: abs(c[0]) + abs(c[1]))
            state.remembered_hub_row = hub[0]
            state.remembered_hub_col = hub[1]

        # Update team role tracking in shared map
        gear = self._current_gear(obs) or "none"
        if self._shared_map:
            self._shared_map.agent_roles[self._agent_id] = gear

        return current_abs

    def _carried_total(self, obs: AgentObservation) -> int:
        from cogames.policy.starter_agent import ELEMENTS
        center = self._starter._center
        total = 0
        for token in obs.tokens:
            if token.location != center:
                continue
            name = token.feature.name
            if name.startswith("inv:"):
                parts = name.split(":", 2)
                if len(parts) >= 2 and parts[1] in ELEMENTS:
                    total += int(token.value)
        return total

    def _known_alignable_junctions(self, state: CrossRoleState) -> set[tuple[int, int]]:
        neutral = {j for j in state.known_neutral_junctions if self._is_alignable(j, state) and j not in state.blacklisted_junctions}
        if neutral:
            return neutral
        return {j for j in state.known_enemy_junctions if self._is_alignable(j, state) and j not in state.blacklisted_junctions}

    def _team_counts(self) -> tuple[int, int]:
        """Return (team_aligners, team_miners) from shared map."""
        if not self._shared_map or not hasattr(self._shared_map, 'agent_roles'):
            return 0, 0
        roles = self._shared_map.agent_roles
        aligners = sum(1 for g in roles.values() if g == "aligner")
        miners = sum(1 for g in roles.values() if g == "miner")
        return aligners, miners

    def _update_progress(self, obs: AgentObservation, state: CrossRoleState) -> None:
        has_heart = self._inventory_count(obs, "heart") > 0
        friendly_count = len(state.known_friendly_junctions)
        carried = self._carried_total(obs)
        current_abs = self._spawn_offset(obs)

        if state.current_skill == "get_heart" and has_heart and not state.last_has_heart:
            self._event(state, "acquired a heart")
        if state.current_skill == "align_junction" and friendly_count > state.last_friendly_junctions:
            self._event(state, f"aligned junction! friendly count {state.last_friendly_junctions}→{friendly_count}")
        if state.current_skill == "deposit_resources" and carried < state.last_carried_total and state.last_carried_total > 0:
            self._event(state, f"deposited resources ({state.last_carried_total}→{carried})")

        state.last_has_heart = has_heart
        state.last_friendly_junctions = friendly_count
        state.last_carried_total = carried

        made_progress = (
            (state.current_skill == "get_heart" and has_heart and not state.last_has_heart)
            or (state.current_skill == "align_junction" and friendly_count > state.last_friendly_junctions)
            or (state.current_skill in {"gear_up_aligner", "gear_up_miner"} and self._current_gear(obs) is not None)
            or (state.current_skill == "deposit_resources" and carried < state.last_carried_total)
            or (state.current_skill == "mine_resources" and carried > state.last_carried_total)
        )

        # near hub check
        near_hub = any(
            abs(current_abs[0] - h[0]) + abs(current_abs[1] - h[1]) <= 1
            for h in state.known_hubs
        )
        near_aligner_station = any(
            abs(current_abs[0] - s[0]) + abs(current_abs[1] - s[1]) <= 1
            for s in state.known_aligner_stations
        )
        near_miner_station = any(
            abs(current_abs[0] - s[0]) + abs(current_abs[1] - s[1]) <= 1
            for s in state.known_miner_stations
        )
        stationary_on_valid_target = (
            (state.current_skill == "get_heart" and near_hub)
            or (state.current_skill == "deposit_resources" and near_hub)
            or (state.current_skill == "align_junction" and current_abs in self._known_alignable_junctions(state))
            or (state.current_skill == "gear_up_aligner" and near_aligner_station)
            or (state.current_skill == "gear_up_miner" and near_miner_station)
        )

        last_action_move = self._feature_value(obs, "last_action_move")
        if made_progress:
            state.no_move_steps = 0
            state.no_progress_on_target_steps = 0
        elif stationary_on_valid_target and not made_progress:
            state.no_move_steps = 0
            state.no_progress_on_target_steps += 1
        elif state.current_skill is not None and last_action_move == 0:
            state.no_move_steps += 1
            state.no_progress_on_target_steps = 0
        else:
            state.no_move_steps = 0
            state.no_progress_on_target_steps = 0

    def _feature_value(self, obs: AgentObservation, feature_name: str) -> int | None:
        for token in obs.tokens:
            if token.feature.name == feature_name:
                return int(token.value)
        return None

    def _hub_visible(self, obs: AgentObservation) -> bool:
        return self._starter._closest_tag_location(obs, self._hub_tags) is not None

    def _plan_skill(self, obs: AgentObservation, state: CrossRoleState) -> None:
        gear = self._current_gear(obs) or "none"
        has_heart = self._inventory_count(obs, "heart") > 0
        carried = self._carried_total(obs)
        known_alignable = self._known_alignable_junctions(state)
        team_aligners, team_miners = self._team_counts()

        prompt = build_cross_role_prompt(
            current_gear=gear,
            has_heart=has_heart,
            carried_resources=carried,
            return_load=self._return_load,
            known_neutral_junctions=len(state.known_neutral_junctions),
            known_friendly_junctions=len(state.known_friendly_junctions),
            known_enemy_junctions=len(state.known_enemy_junctions),
            known_extractors=len(state.known_extractors),
            team_aligners=team_aligners,
            team_miners=team_miners,
            total_agents=self._total_agents,
            hub_known=bool(state.known_hubs),
            current_skill=state.current_skill,
            no_move_steps=state.no_move_steps,
            recent_events=state.recent_events,
        )

        logger.info("agent=%s role=cross_role gear=%s llm_prompt_snippet=...team_aligners=%d,team_miners=%d,junctions=%d",
                    obs.agent_id, gear, team_aligners, team_miners, len(known_alignable))
        started_at = time.perf_counter()
        text = self._planner.complete(prompt)
        latency_ms = (time.perf_counter() - started_at) * 1000.0
        logger.info("agent=%s role=cross_role llm_response_ms=%.1f llm_response=%s",
                    obs.agent_id, latency_ms, text.replace("\n", " "))

        skill, reason = _parse_cross_role_skill(text, set(CROSS_ROLE_SKILL_DESCRIPTIONS))
        was_stuck = bool(state.recent_events and (
            "exited as stuck" in state.recent_events[-1]
            or "exited as stale" in state.recent_events[-1]
            or "timed out after" in state.recent_events[-1]
        ))

        # Scripted fallback if LLM parse fails
        if skill is None:
            if gear == "none":
                skill = "gear_up_miner"  # start as miner by default
            elif gear == "miner":
                skill = "deposit_resources" if carried >= self._return_load else "mine_resources"
            elif gear == "aligner":
                if has_heart and known_alignable:
                    skill = "align_junction"
                elif state.known_hubs:
                    skill = "get_heart"
                else:
                    skill = "explore"
            else:
                skill = "explore"
            reason = f"scripted fallback ({reason})"

        # Hard precondition overrides
        # Miner skills require miner gear
        if skill in {"mine_resources", "deposit_resources"} and gear != "miner":
            if gear == "none":
                skill = "gear_up_miner"
                reason = f"overrode {skill}: need miner gear first"
            elif gear == "aligner":
                # Already aligner — redirect to aligner actions
                if has_heart and known_alignable:
                    skill = "align_junction"
                elif state.known_hubs:
                    skill = "get_heart"
                else:
                    skill = "explore"
                reason = f"overrode miner skill: already has aligner gear"

        # Aligner skills require aligner gear
        if skill in {"get_heart", "align_junction"} and gear != "aligner":
            if gear == "none":
                skill = "gear_up_aligner"
                reason = f"overrode {skill}: need aligner gear first"
            elif gear == "miner":
                # Already miner — redirect to miner actions
                skill = "deposit_resources" if carried >= self._return_load else "mine_resources"
                reason = f"overrode aligner skill: already has miner gear, do miner work"

        # Can't align without heart
        if skill == "align_junction" and gear == "aligner" and not has_heart:
            if state.known_hubs and state.get_heart_timeouts == 0:
                skill = "get_heart"
                reason = "overrode align_junction: need heart first"
            else:
                skill = "explore"
                reason = "overrode align_junction: no heart and hub unknown/depleted"

        # Already have heart — don't waste time getting another
        if skill == "get_heart" and has_heart:
            if known_alignable:
                skill = "align_junction"
                reason = "overrode get_heart: heart already held"
            else:
                skill = "explore"
                reason = "overrode get_heart: heart held, no junction known"

        # Full cargo — deposit first
        if skill == "mine_resources" and gear == "miner" and carried >= self._return_load:
            skill = "deposit_resources"
            reason = "overrode mine: cargo full, deposit first"

        # Hub depleted: stop trying get_heart
        if skill == "get_heart" and state.get_heart_timeouts >= 2:
            if known_alignable and has_heart:
                skill = "align_junction"
            else:
                skill = "explore"
            reason = f"overrode get_heart: {state.get_heart_timeouts} timeouts (hub likely empty)"

        # After stuck: force explore to find alternate path
        if was_stuck and skill in {"gear_up_aligner", "gear_up_miner", "get_heart", "align_junction", "mine_resources", "deposit_resources"}:
            skill = "unstuck"
            reason = f"overrode {skill}: exiting stuck state"

        # Break consecutive unstuck loops
        if skill == "unstuck":
            state.consecutive_unstuck += 1
        else:
            state.consecutive_unstuck = 0
        if state.consecutive_unstuck >= 2 and skill == "unstuck":
            skill = "explore"
            reason = f"overrode unstuck→explore after {state.consecutive_unstuck} consecutive"
            state.consecutive_unstuck = 0

        if skill == "explore":
            state.explore_start_junctions = len(state.known_neutral_junctions)

        state.current_skill = skill
        state.current_reason = reason
        state.skill_steps = 0
        state.no_move_steps = 0
        state.no_progress_on_target_steps = 0
        self._event(state, f"planned {skill}: {reason}")

    def _maybe_finish_skill(self, obs: AgentObservation, state: CrossRoleState) -> None:
        gear = self._current_gear(obs) or "none"
        has_heart = self._inventory_count(obs, "heart") > 0
        carried = self._carried_total(obs)
        friendly_count = len(state.known_friendly_junctions)

        # Natural completions
        if state.current_skill == "gear_up_aligner" and gear == "aligner" and state.skill_steps > 0:
            self._event(state, "gear_up_aligner completed")
            state.current_skill = None
        elif state.current_skill == "gear_up_miner" and gear == "miner" and state.skill_steps > 0:
            self._event(state, "gear_up_miner completed")
            state.current_skill = None
        elif state.current_skill == "get_heart" and has_heart and state.skill_steps > 0:
            self._event(state, "get_heart completed")
            state.get_heart_timeouts = 0
            state.current_skill = None
        elif state.current_skill == "align_junction" and not has_heart and state.skill_steps > 0:
            self._event(state, "align_junction completed (heart spent)")
            state.align_junction_timeouts = 0
            state.current_skill = None
        elif state.current_skill == "deposit_resources" and carried == 0 and state.skill_steps > 0:
            self._event(state, "deposit_resources completed")
            state.current_skill = None
        elif state.current_skill == "mine_resources" and carried >= self._return_load:
            self._event(state, f"mine_resources completed (cargo={carried})")
            state.current_skill = None
        elif state.current_skill == "explore" and len(state.known_neutral_junctions) > state.explore_start_junctions:
            new_j = len(state.known_neutral_junctions) - state.explore_start_junctions
            self._event(state, f"explore completed: found {new_j} new junction(s)")
            state.current_skill = None
        elif state.current_skill == "unstuck" and state.skill_steps >= self._unstuck_horizon:
            self._event(state, "unstuck: completed horizon")
            state.current_skill = None
        # Timeouts
        elif state.current_skill in {"gear_up_aligner", "gear_up_miner"} and state.skill_steps >= self._stuck_threshold * 10:
            self._event(state, f"{state.current_skill} timed out after {state.skill_steps} steps")
            state.current_skill = None
        elif state.current_skill in {"get_heart", "align_junction", "mine_resources", "deposit_resources"} and state.skill_steps >= self._stuck_threshold * 5:
            if state.current_skill == "align_junction":
                state.align_junction_timeouts += 1
                if state.align_junction_timeouts >= 1:
                    # Blacklist stuck junction
                    current_abs = self._spawn_offset(obs)
                    non_bl_neutral = state.known_neutral_junctions - state.blacklisted_junctions
                    non_bl_enemy = state.known_enemy_junctions - state.blacklisted_junctions
                    stuck_junction = self._nearest_known(current_abs, non_bl_neutral or non_bl_enemy)
                    if stuck_junction is not None:
                        state.blacklisted_junctions.add(stuck_junction)
                        state.known_neutral_junctions.discard(stuck_junction)
                        state.known_enemy_junctions.discard(stuck_junction)
                        self._event(state, f"blacklisted stuck junction {stuck_junction}")
                        state.align_junction_timeouts = 0
            elif state.current_skill == "get_heart":
                state.get_heart_timeouts += 1
            self._event(state, f"{state.current_skill} timed out after {state.skill_steps} steps")
            state.current_skill = None
        # Stuck detection
        elif state.current_skill not in {None, "gear_up_aligner", "gear_up_miner"} and state.no_move_steps >= self._stuck_threshold:
            self._event(state, f"{state.current_skill} exited as stuck after {state.no_move_steps} blocked steps")
            # Log detailed stuck debug info
            current_abs = self._spawn_offset(obs)
            gear = self._current_gear(obs)
            logger.info(
                "agent=%s STUCK_DEBUG skill=%s gear=%s pos=%s known_neutral=%d known_friendly=%d "
                "known_hubs=%d known_aligner_stations=%d known_miner_stations=%d known_extractors=%d "
                "no_move_steps=%d skill_steps=%d",
                obs.agent_id, state.current_skill, self._current_gear(obs), current_abs,
                len(state.known_neutral_junctions), len(state.known_friendly_junctions),
                len(state.known_hubs), len(state.known_aligner_stations),
                len(state.known_miner_stations), len(state.known_extractors),
                state.no_move_steps, state.skill_steps,
            )
            state.current_skill = None
        elif state.current_skill not in {None, "gear_up_aligner", "gear_up_miner"} and state.no_progress_on_target_steps >= self._stuck_threshold:
            self._event(state, f"{state.current_skill} exited as stale on target after {state.no_progress_on_target_steps} steps")
            state.current_skill = None

    def _unstuck(self, state: CrossRoleState) -> tuple[Action, CrossRoleState]:
        state.last_mode = "unstuck"
        direction = self._UNSTUCK_DIRECTIONS[state.wander_direction_index % len(self._UNSTUCK_DIRECTIONS)]
        state.wander_direction_index = (state.wander_direction_index + 1) % len(self._UNSTUCK_DIRECTIONS)
        return self._starter._action(f"move_{direction}"), state

    def _gear_up_miner_skill(self, obs: AgentObservation, state: CrossRoleState, current_abs: tuple[int, int]) -> tuple[Action, CrossRoleState]:
        """Navigate to miner station to get miner gear."""
        state.last_mode = "gear_up_miner"
        visible_target = self._starter._closest_tag_location(obs, self._miner_station_tags)
        if visible_target is not None:
            target_abs = self._visible_abs_cell(current_abs, visible_target)
            direction = self._navigate_to_station(state, current_abs, target_abs, avoid_hazards=False)
            if direction:
                action = self._starter._action(f"move_{direction}")
                state.last_move_target = self._move_target(current_abs, direction)
                return action, state
        target_abs = self._nearest_known(current_abs, state.known_miner_stations)
        if target_abs is None:
            # Explore near hub to find miner station
            if state.known_hubs:
                action, base_state = self._explore_near_hub(obs, state)
            else:
                action, base_state = self._explore(obs, state)
            return action, self._copy_with(state, base_state)
        direction = self._navigate_to_station(state, current_abs, target_abs, avoid_hazards=False)
        if direction:
            action = self._starter._action(f"move_{direction}")
            state.last_move_target = self._move_target(current_abs, direction)
            return action, state
        action, base_state = self._move_toward_target(state, current_abs, target_abs)
        return action, self._copy_with(state, base_state)

    def _mine_resources_skill(self, obs: AgentObservation, state: CrossRoleState, current_abs: tuple[int, int]) -> tuple[Action, CrossRoleState]:
        """Mine resources at nearest extractor."""
        state.last_mode = "mine_resources"
        visible_target = self._starter._closest_tag_location(obs, self._starter._extractor_tags)
        if visible_target is not None:
            target_abs = self._visible_abs_cell(current_abs, visible_target)
            action, base_state = self._move_toward_target(state, current_abs, target_abs)
            return action, self._copy_with(state, base_state)
        target_abs = self._nearest_known(current_abs, state.known_extractors)
        if target_abs is None:
            if state.known_hubs:
                action, base_state = self._explore_near_hub(obs, state)
            else:
                action, base_state = self._explore(obs, state)
            return action, self._copy_with(state, base_state)
        action, base_state = self._move_toward_target(state, current_abs, target_abs)
        return action, self._copy_with(state, base_state)

    def _deposit_resources_skill(self, obs: AgentObservation, state: CrossRoleState, current_abs: tuple[int, int]) -> tuple[Action, CrossRoleState]:
        """Navigate to hub and deposit carried resources."""
        state.last_mode = "deposit_resources"
        if not state.known_hubs and state.remembered_hub_row is not None:
            state.known_hubs.add((state.remembered_hub_row, state.remembered_hub_col))
        target_abs = self._nearest_known(current_abs, state.known_hubs)
        if target_abs is None:
            action, base_state = self._explore(obs, state)
            return action, self._copy_with(state, base_state)
        direction = self._navigate_to_station(state, current_abs, target_abs, avoid_hazards=False)
        if direction:
            action = self._starter._action(f"move_{direction}")
            state.last_move_target = self._move_target(current_abs, direction)
            return action, state
        action, base_state = self._move_toward_target(state, current_abs, target_abs)
        return action, self._copy_with(state, base_state)

    def _check_hp(self, obs: AgentObservation, state: CrossRoleState, current_abs: tuple[int, int]) -> bool:
        hp = self._read_hp(obs)
        if hp is None:
            return False
        if hp > state.max_hp_seen:
            state.max_hp_seen = hp
        if state.max_hp_seen <= 0:
            return False
        hp_fraction = hp / state.max_hp_seen
        in_friendly = self._in_friendly_territory(current_abs, state)
        if hp_fraction < _HP_RETREAT_THRESHOLD and not in_friendly:
            if not state.retreating:
                self._event(state, f"HP low ({hp}/{state.max_hp_seen}), retreating")
                state.retreating = True
            return True
        if state.retreating and (in_friendly or hp_fraction > 0.7):
            state.retreating = False
        return False

    def step_with_state(self, obs: AgentObservation, state: CrossRoleState) -> tuple[Action, CrossRoleState]:
        current_abs = self._update_map_memory_cross_role(obs, state)
        self._update_progress(obs, state)

        # HP safety: retreat if low
        if self._check_hp(obs, state, current_abs):
            retreat_targets = state.known_hubs | state.known_friendly_junctions
            if retreat_targets:
                target = self._nearest_known(current_abs, retreat_targets)
                direction = self._navigate_to_station(state, current_abs, target, avoid_hazards=False)
                if direction:
                    action = self._starter._action(f"move_{direction}")
                    state.last_move_target = self._move_target(current_abs, direction)
                    state.skill_steps += 1
                    return action, state
            action, state = self._safe_wander(state, current_abs)
            return action, state

        self._maybe_finish_skill(obs, state)
        if state.current_skill is None:
            self._plan_skill(obs, state)

        # Navigation shake for stuck moves
        if state.current_skill not in {None, "unstuck"} and state.no_move_steps >= 5 and state.no_move_steps % 3 == 0:
            action, state = self._unstuck(state)
            state.skill_steps += 1
            return action, state

        if state.current_skill == "gear_up_aligner":
            action, base_state = self._gear_up(obs, state, current_abs)
            state = self._copy_with(state, base_state)
        elif state.current_skill == "gear_up_miner":
            action, state = self._gear_up_miner_skill(obs, state, current_abs)
        elif state.current_skill == "get_heart":
            action, base_state = self._get_heart(obs, state, current_abs)
            state = self._copy_with(state, base_state)
        elif state.current_skill == "align_junction":
            action, base_state = self._align_neutral(obs, state, current_abs)
            state = self._copy_with(state, base_state)
        elif state.current_skill == "mine_resources":
            action, state = self._mine_resources_skill(obs, state, current_abs)
        elif state.current_skill == "deposit_resources":
            action, state = self._deposit_resources_skill(obs, state, current_abs)
        elif state.current_skill == "explore":
            has_heart = self._inventory_count(obs, "heart") > 0
            if has_heart:
                action, base_state = self._explore_for_alignment(obs, state)
            elif state.known_hubs:
                action, base_state = self._explore_near_hub(obs, state)
            else:
                action, base_state = self._explore(obs, state)
            state = self._copy_with(state, base_state)
        else:
            action, state = self._unstuck(state)

        state.skill_steps += 1
        action_name = action.name if hasattr(action, "name") else ""
        if action_name.startswith("move_"):
            state.last_move_target = self._move_target(current_abs, action_name[len("move_"):])
        return action, state


class MachinaCrossRolePolicy(MultiAgentPolicy):
    """All agents use the cross-role policy: dynamically switch miner/aligner based on team needs."""

    short_names = ["machina_cross_role", "cross_role"]

    def __init__(
        self,
        policy_env_info: PolicyEnvInterface,
        device: str = "cpu",
        return_load: int | str = 40,
        stuck_threshold: int | str = 20,
        unstuck_horizon: int | str = 4,
        llm_api_url: str | None = None,
        llm_model: str | None = "nvidia/llama-3.3-nemotron-super-49b-v1.5",
        llm_api_key_env: str = "OPENROUTER_API_KEY",
        llm_site_url: str | None = None,
        llm_app_name: str = "cogames-voyager",
        llm_timeout_s: float | str = 10.0,
        llm_responder: Callable[[str], str] | None = None,
        llm_local_model_path: str | None = None,
    ):
        super().__init__(policy_env_info, device=device)
        self._shared_map = SharedMap()
        # Add agent_roles tracking to SharedMap
        self._shared_map.agent_roles = {}  # type: ignore[attr-defined]

        self._planner = LLMMinerPlannerClient(
            api_url=llm_api_url,
            model=llm_model,
            api_key_env=llm_api_key_env,
            site_url=llm_site_url,
            app_name=llm_app_name,
            timeout_s=float(llm_timeout_s),
            responder=llm_responder,
            local_model_path=llm_local_model_path,
        )
        self._return_load = int(return_load)
        self._stuck_threshold = int(stuck_threshold)
        self._unstuck_horizon = int(unstuck_horizon)
        self._n_agents = policy_env_info.num_agents
        self._agent_policies: dict[int, StatefulAgentPolicy[CrossRoleState]] = {}

    def agent_policy(self, agent_id: int) -> StatefulAgentPolicy[CrossRoleState]:
        if agent_id not in self._agent_policies:
            impl = LLMCrossRolePolicyImpl(
                self._policy_env_info,
                agent_id,
                planner=self._planner,
                shared_map=self._shared_map,
                return_load=self._return_load,
                stuck_threshold=self._stuck_threshold,
                unstuck_horizon=self._unstuck_horizon,
                total_agents=self._n_agents,
            )
            self._agent_policies[agent_id] = StatefulAgentPolicy(
                impl,
                self._policy_env_info,
                agent_id=agent_id,
            )
        return self._agent_policies[agent_id]
