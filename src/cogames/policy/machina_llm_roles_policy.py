from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass, field, replace
from typing import Callable

from cogames.policy.aligner_agent import (
    AlignerPolicyImpl, AlignerState, SharedMap, _FRIENDLY_TERRITORY_DISTANCE, _HP_RETREAT_THRESHOLD,
)
from cogames.policy.llm_aligner_prompt import ALIGNER_SKILL_DESCRIPTIONS, build_llm_aligner_prompt
from cogames.policy.llm_miner_policy import LLMMinerPlannerClient, LLMMinerPolicyImpl, LLMMinerState
from cogames.policy.scout_agent import ScoutExplorerPolicyImpl, ScoutState
from mettagrid.policy.policy import MultiAgentPolicy, StatefulAgentPolicy, StatefulPolicyImpl
from mettagrid.policy.policy_env_interface import PolicyEnvInterface
from mettagrid.simulator import Action
from mettagrid.simulator.interface import AgentObservation

logger = logging.getLogger("cogames.policy.machina_llm_roles")


def _parse_role_skill_choice(text: str, valid_skills: set[str]) -> tuple[str | None, str]:
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
    normalized_skill = {"unstick": "unstuck"}.get(skill, skill)
    return (normalized_skill if normalized_skill in valid_skills else None, str(reason))


@dataclass
class LLMAlignerState(AlignerState):
    current_skill: str | None = None
    current_reason: str = ""
    skill_steps: int = 0
    no_move_steps: int = 0
    no_progress_on_target_steps: int = 0
    last_has_heart: bool = False
    last_heart_count: int = 0
    last_friendly_junctions: int = 0
    consecutive_unstuck: int = 0
    explore_start_junctions: int = 0
    align_neutral_timeouts: int = 0
    get_heart_timeouts: int = 0
    recent_events: list[str] = field(default_factory=list)
    # HP monitoring
    max_hp_seen: int = 0
    retreating: bool = False


class LLMAlignerPolicyImpl(AlignerPolicyImpl, StatefulPolicyImpl[LLMAlignerState]):
    _UNSTUCK_DIRECTIONS = ("north", "east", "south", "west")

    def __init__(
        self,
        policy_env_info: PolicyEnvInterface,
        agent_id: int,
        planner: LLMMinerPlannerClient,
        stuck_threshold: int,
        unstuck_horizon: int,
        shared_map: SharedMap | None = None,
        scripted: bool = False,
    ) -> None:
        super().__init__(policy_env_info, agent_id, shared_map=shared_map)
        self._planner = planner
        self._stuck_threshold = stuck_threshold
        self._unstuck_horizon = unstuck_horizon
        self._scripted = scripted

    def initial_agent_state(self) -> LLMAlignerState:
        base = super().initial_agent_state()
        state = LLMAlignerState(
            wander_direction_index=base.wander_direction_index,
            wander_steps_remaining=base.wander_steps_remaining,
            last_mode=base.last_mode,
        )
        self._bind_shared_map(state)
        return state

    def _copy_with(self, state: LLMAlignerState, base: AlignerState) -> LLMAlignerState:
        sm = self._shared_map
        result = replace(
            state,
            wander_direction_index=base.wander_direction_index,
            wander_steps_remaining=base.wander_steps_remaining,
            last_mode=base.last_mode,
            # With shared map: preserve shared references; without: copy sets
            known_free_cells=sm.known_free_cells if sm else set(base.known_free_cells),
            blocked_cells=sm.blocked_cells if sm else set(base.blocked_cells),
            move_blocked_cells=sm.move_blocked_cells if sm else set(base.move_blocked_cells),
            known_hubs=sm.known_hubs if sm else set(base.known_hubs),
            known_aligner_stations=sm.known_aligner_stations if sm else set(base.known_aligner_stations),
            known_neutral_junctions=sm.known_neutral_junctions if sm else set(base.known_neutral_junctions),
            known_friendly_junctions=sm.known_friendly_junctions if sm else set(base.known_friendly_junctions),
            known_enemy_junctions=sm.known_enemy_junctions if sm else set(base.known_enemy_junctions),
            known_hazard_stations=sm.known_hazard_stations if sm else set(base.known_hazard_stations),
            current_skill=state.current_skill,
            current_reason=state.current_reason,
            skill_steps=state.skill_steps,
            no_move_steps=state.no_move_steps,
            no_progress_on_target_steps=state.no_progress_on_target_steps,
            last_has_heart=state.last_has_heart,
            last_heart_count=state.last_heart_count,
            last_friendly_junctions=state.last_friendly_junctions,
            consecutive_unstuck=state.consecutive_unstuck,
            explore_start_junctions=state.explore_start_junctions,
            align_neutral_timeouts=state.align_neutral_timeouts,
            get_heart_timeouts=state.get_heart_timeouts,
            recent_events=list(state.recent_events),
            blacklisted_junctions=set(state.blacklisted_junctions),
            move_cooldowns=dict(state.move_cooldowns),
            steps_since_last_move=state.steps_since_last_move,
        )
        return result

    def _event(self, state: LLMAlignerState, message: str) -> None:
        state.recent_events.append(message)
        del state.recent_events[:-10]

    def _feature_value(self, obs: AgentObservation, feature_name: str) -> int | None:
        for token in obs.tokens:
            if token.feature.name == feature_name:
                return int(token.value)
        return None

    def _hub_visible(self, obs: AgentObservation) -> bool:
        return self._starter._closest_tag_location(obs, self._hub_tags) is not None

    def _known_alignable_junctions(self, state: LLMAlignerState) -> set[tuple[int, int]]:
        # Combine neutral and enemy junctions — recapturing enemy is a +2 swing
        return {j for j in (state.known_neutral_junctions)
                if self._is_alignable(j, state) and j not in state.blacklisted_junctions}

    def _update_progress(self, obs: AgentObservation, state: LLMAlignerState) -> None:
        has_heart = self._inventory_count(obs, "heart") > 0
        heart_count = self._inventory_count(obs, "heart")
        friendly_count = len(state.known_friendly_junctions)
        current_abs = self._spawn_offset(obs)
        if state.current_skill == "get_heart" and has_heart and not state.last_has_heart:
            self._event(state, "acquired a heart")
        if state.current_skill == "align_neutral" and friendly_count > state.last_friendly_junctions:
            self._event(state, f"friendly junction count increased from {state.last_friendly_junctions} to {friendly_count}")

        heart_increased = state.current_skill == "get_heart" and heart_count > state.last_heart_count
        state.last_has_heart = has_heart
        state.last_heart_count = heart_count
        state.last_friendly_junctions = friendly_count
        last_action_move = self._feature_value(obs, "last_action_move")
        made_progress = (
            (state.current_skill == "get_heart" and (heart_increased or (has_heart and not state.last_has_heart)))
            or (state.current_skill == "align_neutral" and friendly_count > state.last_friendly_junctions)
            or (state.current_skill == "gear_up" and self._current_gear(obs) == "aligner")
        )
        # Hub cells are blocked objects — agents stand adjacent, never on the hub cell itself.
        # Use Manhattan distance ≤ 1 for get_heart so navigation-shake doesn't fire while waiting.
        _hubs = state.verified_hubs if state.verified_hubs else state.known_hubs
        near_hub = any(
            abs(current_abs[0] - h[0]) + abs(current_abs[1] - h[1]) <= 1
            for h in _hubs
        )
        near_aligner_station = any(
            abs(current_abs[0] - s[0]) + abs(current_abs[1] - s[1]) <= 1
            for s in state.known_aligner_stations
        )
        stationary_on_valid_target = (
            (state.current_skill == "get_heart" and near_hub)
            or (state.current_skill == "align_neutral" and current_abs in self._known_alignable_junctions(state))
            or (state.current_skill == "gear_up" and near_aligner_station)
            or (state.current_skill == "defend" and current_abs in state.known_friendly_junctions)
        )
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

    def _plan_skill(self, obs: AgentObservation, state: LLMAlignerState) -> None:
        has_aligner = self._current_gear(obs) == "aligner"
        has_heart = self._inventory_count(obs, "heart") > 0
        known_alignable_junctions = self._known_alignable_junctions(state)

        if self._scripted:
            # Skip LLM call entirely — use deterministic rule-based planner
            skill = None
            reason = "scripted mode"
            logger.info("agent=%s role=aligner scripted_plan has_aligner=%s has_heart=%s alignable=%d",
                        obs.agent_id, has_aligner, has_heart, len(known_alignable_junctions))
        else:
            prompt = build_llm_aligner_prompt(
                has_aligner=has_aligner,
                has_heart=has_heart,
                hub_visible=self._hub_visible(obs),
                known_hubs=len(state.known_hubs),
                known_neutral_junctions=len(state.known_neutral_junctions),
                known_alignable_junctions=len(known_alignable_junctions),
                known_friendly_junctions=len(state.known_friendly_junctions),
                current_skill=state.current_skill,
                no_move_steps=state.no_move_steps,
                recent_events=state.recent_events,
            )
            logger.info("agent=%s role=aligner llm_prompt=%s", obs.agent_id, prompt.replace("\n", " | "))
            started_at = time.perf_counter()
            try:
                text = self._planner.complete(prompt)
            except Exception as e:
                latency_ms = (time.perf_counter() - started_at) * 1000.0
                logger.warning("agent=%s role=aligner llm_error_ms=%.1f error=%s", obs.agent_id, latency_ms, e)
                text = ""
            else:
                latency_ms = (time.perf_counter() - started_at) * 1000.0
                logger.info(
                    "agent=%s role=aligner llm_response_ms=%.1f llm_response=%s",
                    obs.agent_id,
                    latency_ms,
                    text.replace("\n", " "),
                )
            skill, reason = _parse_role_skill_choice(text, set(ALIGNER_SKILL_DESCRIPTIONS))
        was_stuck = bool(state.recent_events and ("exited as stuck" in state.recent_events[-1] or "exited as stale" in state.recent_events[-1] or "timed out after" in state.recent_events[-1]))
        if skill is None:
            if not has_aligner:
                skill = "explore" if was_stuck else "gear_up"
            elif not has_heart and state.known_hubs and not was_stuck:
                skill = "get_heart"
            elif known_alignable_junctions and not was_stuck:
                skill = "align_neutral"
            else:
                skill = "explore"
            reason = f"scripted fallback ({reason})"
        # After stuck exit: force explore to find alternate path (prevent gear_up→stuck→gear_up loop)
        if not has_aligner and skill == "gear_up" and was_stuck:
            reason = "overrode gear_up to explore after stuck exit (find alternate path to aligner station)"
            skill = "explore"
        # Allow explore/unstuck after stuck exit even without aligner (find alternate path to station)
        if not has_aligner and skill not in {"gear_up", "unstuck", "explore"}:
            if was_stuck:
                reason = f"overrode {skill} to explore after stuck exit (seeking new path to aligner station)"
                skill = "explore"
            else:
                reason = f"overrode {skill} to gear_up because aligner gear is missing"
                skill = "gear_up"
        if has_aligner and skill == "gear_up":
            if has_heart and state.known_neutral_junctions:
                reason = "overrode gear_up to align_neutral because aligner gear is already equipped and a target is known"
                skill = "align_neutral"
            elif not has_heart:
                reason = "overrode gear_up to get_heart because aligner gear is already equipped"
                skill = "get_heart"
            else:
                reason = "overrode gear_up to explore because aligner gear is already equipped"
                skill = "explore"
        if has_aligner and not has_heart and state.known_hubs and skill == "explore" and not was_stuck:
            reason = f"overrode {skill} to get_heart because aligner gear is equipped and a hub is known"
            skill = "get_heart"
        if has_aligner and not has_heart and skill == "align_neutral":
            reason = "overrode align_neutral to get_heart because no heart is held"
            skill = "get_heart"
        if has_aligner and has_heart and known_alignable_junctions and skill in {"explore", "get_heart"} and not was_stuck:
            if skill == "get_heart":
                heart_count = self._inventory_count(obs, "heart")
                current_abs = self._spawn_offset(obs)
                _vh = state.verified_hubs if state.verified_hubs else state.known_hubs
                near_hub = any(
                    abs(current_abs[0] - h[0]) + abs(current_abs[1] - h[1]) <= 2
                    for h in _vh
                )
                if heart_count < 6 and near_hub:
                    pass
                else:
                    reason = f"overrode get_heart to align_neutral ({heart_count} hearts, not near hub)"
                    skill = "align_neutral"
            else:
                reason = f"overrode {skill} to align_neutral because an alignable neutral junction is already known"
                skill = "align_neutral"
        # After stuck/timeout with gear+heart+junction: try unstuck to escape navigation deadlock
        if has_aligner and has_heart and known_alignable_junctions and skill == "align_neutral" and was_stuck:
            reason = "overrode align_neutral to unstuck after stuck exit (escape navigation deadlock near junction)"
            skill = "unstuck"
        # Prevent immediate-completion loops: get_heart already done if has_heart=True
        # Exception: near hub with <5 hearts, allow accumulation
        if has_aligner and has_heart and skill == "get_heart":
            heart_count = self._inventory_count(obs, "heart")
            current_abs = self._spawn_offset(obs)
            _vh2 = state.verified_hubs if state.verified_hubs else state.known_hubs
            near_hub = any(
                abs(current_abs[0] - h[0]) + abs(current_abs[1] - h[1]) <= 2
                for h in _vh2
            )
            if heart_count < 6 and near_hub:
                pass
            elif known_alignable_junctions:
                reason = f"overrode get_heart to align_neutral ({heart_count} hearts held)"
                skill = "align_neutral"
            else:
                reason = "overrode get_heart to explore (heart already held, no target known)"
                skill = "explore"
        # After get_heart timeout/stuck with no heart: unstuck first to escape navigation deadlock
        if has_aligner and not has_heart and skill == "get_heart" and was_stuck and state.known_hubs:
            reason = "overrode get_heart to unstuck after stuck exit (escape navigation deadlock near hub)"
            skill = "unstuck"
        # Hub likely depleted: after 1+ get_heart timeout, defend friendly junctions instead
        if has_aligner and not has_heart and skill == "get_heart" and state.get_heart_timeouts >= 1 and state.known_friendly_junctions:
            reason = f"overrode get_heart to defend after {state.get_heart_timeouts} timeouts (hub likely empty)"
            skill = "defend"
        # Break explore→stuck loop when agent has gear+heart but no known junctions: try unstuck
        if has_aligner and has_heart and not known_alignable_junctions and skill == "explore" and was_stuck:
            reason = "overrode explore to unstuck after stuck exit (try escape moves to find junctions)"
            skill = "unstuck"
        # Break consecutive unstuck loops: after 2+ unstuck in a row, force explore to find new routes
        if skill == "unstuck":
            state.consecutive_unstuck += 1
        else:
            state.consecutive_unstuck = 0
        if state.consecutive_unstuck >= 2 and skill == "unstuck":
            skill = "explore"
            reason = f"overrode unstuck to explore after {state.consecutive_unstuck} consecutive unstuck calls"
            state.consecutive_unstuck = 0
        # Heart queue management: avoid too many aligners rushing to hub when few hearts available
        # Allow at least 2 aligners simultaneously to reduce idle time
        if skill == "get_heart" and self._shared_map is not None:
            sm = self._shared_map
            available_hearts = max(0, sm.initial_hub_hearts + sm.hearts_crafted_estimate - sm.hub_hearts_withdrawn)
            already_getting = len(sm.agents_getting_hearts - {obs.agent_id})
            if already_getting >= max(3, available_hearts):
                skill = "explore"
                reason = f"heart queue: {already_getting} aligners en route, ~{available_hearts} hearts avail — exploring instead"
        if skill == "get_heart" and self._shared_map is not None:
            self._shared_map.agents_getting_hearts.add(obs.agent_id)
        if skill == "explore":
            state.explore_start_junctions = len(state.known_neutral_junctions) + len(state.known_enemy_junctions)
        state.current_skill = skill
        state.current_reason = reason
        state.skill_steps = 0
        state.no_move_steps = 0
        state.no_progress_on_target_steps = 0
        self._event(state, f"planner selected {skill}: {reason}")

    def _maybe_finish_skill(self, obs: AgentObservation, state: LLMAlignerState) -> None:
        has_heart = self._inventory_count(obs, "heart") > 0
        has_aligner = self._current_gear(obs) == "aligner"
        if not has_aligner and state.current_skill not in {None, "gear_up", "unstuck", "explore"}:
            self._event(state, f"gear lost during {state.current_skill} — switching to gear_up")
            state.current_skill = None
            return
        if state.current_skill == "gear_up" and has_aligner and state.skill_steps > 0:
            self._event(state, "gear_up completed after acquiring aligner gear")
            state.current_skill = None
        elif state.current_skill == "get_heart" and has_heart and state.skill_steps > 0:
            heart_count = self._inventory_count(obs, "heart")
            current_abs = self._spawn_offset(obs)
            _vh3 = state.verified_hubs if state.verified_hubs else state.known_hubs
            near_hub = any(
                abs(current_abs[0] - h[0]) + abs(current_abs[1] - h[1]) <= 2
                for h in _vh3
            )
            if heart_count < 5 and near_hub and state.no_progress_on_target_steps < 3:
                pass
            else:
                self._event(state, f"get_heart completed with {heart_count} heart(s)")
                state.get_heart_timeouts = 0
                sm = self._shared_map
                if sm is not None:
                    sm.hub_hearts_withdrawn += heart_count
                    sm.agents_getting_hearts.discard(obs.agent_id)
                state.current_skill = None
        elif state.current_skill == "defend" and has_heart:
            self._event(state, "defend ended: acquired heart while defending")
            state.get_heart_timeouts = 0
            state.current_skill = None
        elif state.current_skill == "defend" and state.skill_steps >= self._stuck_threshold * 50:
            self._event(state, "defend ended: trying get_heart again")
            state.get_heart_timeouts = 0  # reset to allow another get_heart attempt
            state.current_skill = None
        elif state.current_skill == "align_neutral" and not has_heart and state.skill_steps > 0:
            self._event(state, "align_neutral completed after spending heart")
            state.current_skill = None
            state.align_neutral_timeouts = 0
        elif state.current_skill == "explore" and (
            len(state.known_neutral_junctions) + len(state.known_enemy_junctions) > state.explore_start_junctions
        ):
            new_total = len(state.known_neutral_junctions) + len(state.known_enemy_junctions) - state.explore_start_junctions
            self._event(state, f"explore completed after discovering {new_total} new alignable junction(s)")
            state.current_skill = None
        elif state.current_skill == "explore" and state.skill_steps >= self._stuck_threshold * 3:
            # Cap explore duration to prevent long idle periods when no junctions nearby
            self._event(state, f"explore capped after {state.skill_steps} steps without finding junctions")
            state.current_skill = None
        elif state.current_skill == "unstuck" and state.skill_steps >= self._unstuck_horizon:
            self._event(state, "unstuck finished its bounded horizon")
            state.current_skill = None
        elif state.current_skill == "gear_up" and state.skill_steps >= self._stuck_threshold * 10:
            self._event(state, f"gear_up timed out after {state.skill_steps} steps without completion")
            state.current_skill = None
        elif state.current_skill in {"get_heart", "align_neutral"} and state.skill_steps >= self._stuck_threshold * 5:
            if state.current_skill == "align_neutral":
                state.align_neutral_timeouts += 1
                # After 1+ timeout, forget the nearest stuck junction to try a different target
                if state.align_neutral_timeouts >= 1:
                    current_abs = self._spawn_offset(obs)
                    non_blacklisted_neutral = state.known_neutral_junctions - state.blacklisted_junctions
                    non_blacklisted_enemy = state.known_enemy_junctions - state.blacklisted_junctions
                    if non_blacklisted_neutral:
                        stuck_junction = self._nearest_known(current_abs, non_blacklisted_neutral)
                        if stuck_junction is not None:
                            state.blacklisted_junctions.add(stuck_junction)
                            self._event(state, f"blacklisted stuck neutral junction at {stuck_junction} after {state.align_neutral_timeouts} timeouts")
                            state.align_neutral_timeouts = 0
                    elif non_blacklisted_enemy:
                        stuck_junction = self._nearest_known(current_abs, non_blacklisted_enemy)
                        if stuck_junction is not None:
                            state.blacklisted_junctions.add(stuck_junction)
                            self._event(state, f"blacklisted stuck enemy junction at {stuck_junction} after {state.align_neutral_timeouts} timeouts")
                            state.align_neutral_timeouts = 0
            elif state.current_skill == "get_heart":
                state.get_heart_timeouts += 1
            self._event(state, f"{state.current_skill} timed out after {state.skill_steps} steps without completion")
            state.current_skill = None
        elif state.current_skill not in {None, "gear_up"} and state.no_move_steps >= self._stuck_threshold:
            self._event(state, f"{state.current_skill} exited as stuck after {state.no_move_steps} blocked steps")
            state.current_skill = None
        elif state.current_skill not in {None, "gear_up"} and state.no_progress_on_target_steps >= self._stuck_threshold:
            self._event(state, f"{state.current_skill} exited as stale on target after {state.no_progress_on_target_steps} steps without progress")
            state.current_skill = None

    def _unstuck(self, state: LLMAlignerState) -> tuple[Action, LLMAlignerState]:
        state.last_mode = "unstuck"
        direction = self._UNSTUCK_DIRECTIONS[state.wander_direction_index % len(self._UNSTUCK_DIRECTIONS)]
        state.wander_direction_index = (state.wander_direction_index + 1) % len(self._UNSTUCK_DIRECTIONS)
        return self._starter._action(f"move_{direction}"), state

    _ALIGNER_HP_RETREAT_THRESHOLD = 0.35
    _ALIGNER_HP_RESUME_THRESHOLD = 0.50

    def _read_hp(self, obs: AgentObservation) -> int | None:
        center = self._starter._center
        for token in obs.tokens:
            if token.location != center:
                continue
            if token.feature.name == "inv:hp":
                return int(token.value)
        return None

    def _check_hp(self, obs: AgentObservation, state: LLMAlignerState, current_abs) -> bool:
        """Check HP and update retreat state. Returns True if agent should retreat."""
        hp = self._read_hp(obs)
        if hp is None:
            return False
        if hp > state.max_hp_seen:
            state.max_hp_seen = hp
        if state.max_hp_seen <= 0:
            return False
        hp_fraction = hp / state.max_hp_seen
        in_friendly = self._in_friendly_territory(current_abs, state)
        if hp_fraction < self._ALIGNER_HP_RETREAT_THRESHOLD and not in_friendly:
            if not state.retreating:
                logger.info("agent=%s HP_LOW hp=%d/%d (%.0f%%) retreating to friendly territory",
                            obs.agent_id, hp, state.max_hp_seen, hp_fraction * 100)
                self._event(state, f"HP low ({hp}/{state.max_hp_seen}), retreating")
                state.retreating = True
            return True
        if state.retreating and (in_friendly or hp_fraction > self._ALIGNER_HP_RESUME_THRESHOLD):
            logger.info("agent=%s HP_OK hp=%d/%d in_friendly=%s resuming",
                        obs.agent_id, hp, state.max_hp_seen, in_friendly)
            state.retreating = False
        return False

    def step_with_state(self, obs: AgentObservation, state: LLMAlignerState) -> tuple[Action, LLMAlignerState]:
        try:
            return self._step_impl(obs, state)
        except Exception as e:
            logger.warning("agent=%s role=aligner step_error=%s — returning noop", obs.agent_id, e)
            return self._starter._action("noop"), state

    def _step_impl(self, obs: AgentObservation, state: LLMAlignerState) -> tuple[Action, LLMAlignerState]:
        current_abs = self._update_map_memory(obs, state)
        self._update_progress(obs, state)

        # ── Team coordination: sync shared state ──
        sm = self._shared_map
        if sm is not None:
            sm.agent_positions[obs.agent_id] = current_abs
            if state.current_skill != "align_neutral":
                sm.aligner_targets.pop(obs.agent_id, None)
            if state.current_skill != "get_heart":
                sm.agents_getting_hearts.discard(obs.agent_id)

        # ── HP safety: retreat to hub/friendly territory if HP is low ──
        if self._check_hp(obs, state, current_abs):
            # Retreat to nearest hub or friendly junction
            _retreat_hubs = state.verified_hubs if state.verified_hubs else state.known_hubs
            retreat_targets = _retreat_hubs | state.known_friendly_junctions
            if retreat_targets:
                target = self._nearest_known(current_abs, retreat_targets)
                direction = self._navigate_to_station(state, current_abs, target, avoid_hazards=False)
                if direction:
                    action = self._starter._action(f"move_{direction}")
                    state.last_move_target = self._move_target(current_abs, direction)
                    state.skill_steps += 1
                    return action, state
            # No known retreat target: wander safely
            action, state = self._safe_wander(state, current_abs)
            return action, state

        self._maybe_finish_skill(obs, state)
        if state.current_skill is None:
            self._plan_skill(obs, state)

        # Navigation shake: after 5 consecutive blocked moves, every 3rd step try a random direction
        # This breaks BFS deadlocks caused by agent-occupied cells
        if state.current_skill not in {None, "unstuck"} and state.no_move_steps >= 5 and state.no_move_steps % 3 == 0:
            action, state = self._unstuck(state)
            state.skill_steps += 1
            return action, state

        if state.current_skill == "gear_up":
            action, base_state = self._gear_up(obs, state, current_abs)
            state = self._copy_with(state, base_state)
        elif state.current_skill == "get_heart":
            action, base_state = self._get_heart(obs, state, current_abs)
            state = self._copy_with(state, base_state)
        elif state.current_skill == "align_neutral":
            # Junction coordination: avoid targeting same junction as other aligner
            sm = self._shared_map
            if sm is not None:
                targeted_by_others = {
                    t for aid, t in sm.aligner_targets.items()
                    if aid != obs.agent_id and t is not None
                }
                if targeted_by_others:
                    saved_bl = set(state.blacklisted_junctions)
                    state.blacklisted_junctions |= targeted_by_others
                    action, base_state = self._align_neutral(obs, state, current_abs)
                    state.blacklisted_junctions = saved_bl
                else:
                    action, base_state = self._align_neutral(obs, state, current_abs)
                # Record our predicted target (excluding others' targets)
                bl = state.blacklisted_junctions
                alignable = {j for j in (state.known_neutral_junctions)
                            if self._is_alignable(j, state) and j not in bl and j not in targeted_by_others}
                sm.aligner_targets[obs.agent_id] = self._cascade_priority_target(current_abs, alignable, state)
            else:
                action, base_state = self._align_neutral(obs, state, current_abs)
            state = self._copy_with(state, base_state)
        elif state.current_skill == "defend":
            # Navigate to nearest friendly junction and hold position
            current_abs = self._spawn_offset(obs)
            if current_abs in state.known_friendly_junctions:
                # Already on junction - stand and defend (noop)
                action = self._starter._action("noop")
            elif state.known_friendly_junctions:
                target = self._nearest_known(current_abs, state.known_friendly_junctions)
                direction = self._navigate_to_station(state, current_abs, target, avoid_hazards=False)
                if direction:
                    action = self._starter._action(f"move_{direction}")
                    state.last_move_target = self._move_target(current_abs, direction)
                else:
                    action, base_state = self._explore(obs, state)
                    state = self._copy_with(state, base_state)
            else:
                action, base_state = self._explore(obs, state)
                state = self._copy_with(state, base_state)
        elif state.current_skill == "explore":
            if self._inventory_count(obs, "heart") > 0:
                action, base_state = self._explore_for_alignment(obs, state)
            elif state.known_friendly_junctions:
                # Heartless aligner with friendly junctions: explore alignment frontier
                # to discover new junctions for when hearts become available
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


class MachinaLLMRolesPolicy(MultiAgentPolicy):
    short_names = ["machina_llm_roles", "llm_team3"]

    def __init__(
        self,
        policy_env_info: PolicyEnvInterface,
        device: str = "cpu",
        num_aligners: int | str = "auto",
        aligner_ids: str = "",
        num_scouts: int | str = "auto",
        scout_ids: str = "",
        return_load: int | str = 40,
        stuck_threshold: int | str = 15,
        unstuck_horizon: int | str = 4,
        llm_api_url: str | None = None,
        llm_model: str | None = "nvidia/llama-3.3-nemotron-super-49b-v1.5",
        llm_api_key_env: str = "OPENROUTER_API_KEY",
        llm_site_url: str | None = None,
        llm_app_name: str = "cogames-voyager",
        llm_timeout_s: float | str = 10.0,
        llm_responder: Callable[[str], str] | None = None,
        llm_local_model_path: str | None = None,
        scripted_miners: bool | str = "auto",
        scripted_aligners: bool | str = "auto",
        initial_hub_hearts: int | str = 255,
    ):
        super().__init__(policy_env_info, device=device)
        n_agents = policy_env_info.num_agents

        # Resolve scripted_miners: "auto" means always True (LLM API unavailable on tournament server)
        sm_str = str(scripted_miners).lower()
        if sm_str == "auto":
            self._scripted_miners = True
        else:
            self._scripted_miners = sm_str in ("true", "1", "yes")
        logger.info("scripted_miners=%s (n_agents=%d, raw=%s)", self._scripted_miners, n_agents, scripted_miners)

        # Resolve scripted_aligners: "auto" means always True (LLM API unavailable on tournament server)
        sa_str = str(scripted_aligners).lower()
        if sa_str == "auto":
            self._scripted_aligners = True
        else:
            self._scripted_aligners = sa_str in ("true", "1", "yes")
        logger.info("scripted_aligners=%s (n_agents=%d, raw=%s)", self._scripted_aligners, n_agents, scripted_aligners)

        self._shared_map = SharedMap()  # ONE map, shared by ALL agents
        self._shared_map.initial_hub_hearts = int(initial_hub_hearts)

        # Target aligner fraction for proportional role assignment.
        # In tournament, we may only control a subset of agents (e.g. 4 of 8).
        # Static ID-based assignment (aligner_ids={0..4}) causes ALL our agents
        # to become aligners when we get IDs 0-3, leaving zero miners.
        # Fix: assign roles dynamically as agents register via agent_policy().
        parsed_aligner_ids = tuple(int(p.strip()) for p in aligner_ids.split(",") if p.strip())
        if parsed_aligner_ids:
            self._static_aligner_ids: frozenset[int] | None = frozenset(parsed_aligner_ids)
            self._aligner_fraction = 0.0  # unused when static
        else:
            na_str = str(num_aligners).lower()
            self._static_aligner_ids = None
            if na_str == "auto":
                self._aligner_fraction = 7.0 / 8.0
            else:
                self._aligner_fraction = int(num_aligners) / max(n_agents, 1)
        self._assigned_roles: dict[int, str] = {}
        self._n_aligners_assigned = 0
        self._n_miners_assigned = 0
        logger.info("role_assignment mode=%s aligner_fraction=%.3f (n_agents=%d)",
                     "static" if self._static_aligner_ids else "proportional",
                     self._aligner_fraction, n_agents)

        # Resolve scout IDs: "auto" means 0 scouts (scouts are fragile)
        parsed_scout_ids = tuple(int(p.strip()) for p in scout_ids.split(",") if p.strip())
        if parsed_scout_ids:
            self._scout_ids = frozenset(parsed_scout_ids)
        else:
            ns_str = str(num_scouts).lower()
            n_scouts = 0 if ns_str == "auto" else int(num_scouts)
            self._scout_ids = frozenset()
        logger.info("num_scouts=%d (n_agents=%d, raw=%s)", len(self._scout_ids), n_agents, num_scouts)

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
        self._agent_policies: dict[int, StatefulAgentPolicy[LLMAlignerState | LLMMinerState | ScoutState]] = {}

    def _assign_role(self, agent_id: int) -> str:
        if agent_id in self._scout_ids:
            return "scout"
        if self._static_aligner_ids is not None:
            return "aligner" if agent_id in self._static_aligner_ids else "miner"
        if agent_id in self._assigned_roles:
            return self._assigned_roles[agent_id]
        total = self._n_aligners_assigned + self._n_miners_assigned
        target_aligners = round(self._aligner_fraction * (total + 1))
        if self._n_aligners_assigned < target_aligners:
            role = "aligner"
            self._n_aligners_assigned += 1
        else:
            role = "miner"
            self._n_miners_assigned += 1
        self._assigned_roles[agent_id] = role
        return role

    def agent_policy(self, agent_id: int) -> StatefulAgentPolicy[LLMAlignerState | LLMMinerState | ScoutState]:
        if agent_id not in self._agent_policies:
            role = self._assign_role(agent_id)
            logger.info("ROLE_ASSIGNMENT agent=%d role=%s scripted_miners=%s", agent_id, role, self._scripted_miners)
            if role == "aligner":
                impl = LLMAlignerPolicyImpl(
                    self._policy_env_info,
                    agent_id,
                    planner=self._planner,
                    stuck_threshold=self._stuck_threshold,
                    unstuck_horizon=self._unstuck_horizon,
                    shared_map=self._shared_map,
                    scripted=self._scripted_aligners,
                )
            elif role == "scout":
                # Scouts are offset across the grid so multiple scouts cover
                # different sections; the last scout in the set gets offset=0.75.
                sorted_scouts = sorted(self._scout_ids)
                scout_rank = sorted_scouts.index(agent_id)
                offset_fraction = scout_rank / max(len(sorted_scouts), 1)
                impl = ScoutExplorerPolicyImpl(
                    self._policy_env_info,
                    agent_id,
                    grid_offset_fraction=offset_fraction,
                    shared_map=self._shared_map,
                )
            else:
                impl = LLMMinerPolicyImpl(
                    self._policy_env_info,
                    agent_id,
                    planner=None if self._scripted_miners else self._planner,
                    return_load=self._return_load,
                    stuck_threshold=self._stuck_threshold,
                    unstuck_horizon=self._unstuck_horizon,
                    shared_map=self._shared_map,
                )
            self._agent_policies[agent_id] = StatefulAgentPolicy(
                impl,
                self._policy_env_info,
                agent_id=agent_id,
            )
        return self._agent_policies[agent_id]
