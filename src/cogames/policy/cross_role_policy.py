"""Cross-role policy: agents dynamically choose aligner or miner role based on team needs.

Instead of fixed role assignment, each agent asks "what does the team need now?"
and picks skills from both aligner and miner skill sets accordingly.
"""

from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass, field, replace
from typing import Callable

from cogames.policy.aligner_agent import (
    AlignerPolicyImpl,
    SharedMap,
    _HUB_ALIGN_DISTANCE,
    _HP_RETREAT_THRESHOLD,
    _JUNCTION_ALIGN_DISTANCE,
)
from cogames.policy.llm_miner_policy import LLMMinerPlannerClient, LLMMinerPolicyImpl, LLMMinerState
from cogames.policy.llm_skills import MinerSkillImpl, MinerSkillState
from mettagrid.policy.policy import MultiAgentPolicy, StatefulAgentPolicy, StatefulPolicyImpl
from mettagrid.policy.policy_env_interface import PolicyEnvInterface
from mettagrid.simulator import Action
from mettagrid.simulator.interface import AgentObservation

logger = logging.getLogger("cogames.policy.cross_role")

Coord = tuple[int, int]

CROSS_ROLE_SKILLS = {
    "gear_up_aligner": "Route to the aligner station and acquire aligner gear.",
    "gear_up_miner": "Route to the miner station and acquire miner gear.",
    "get_heart": "Route to the hub and obtain a heart (requires aligner gear).",
    "align_neutral": "Route to a neutral junction and align it (requires aligner gear + heart).",
    "mine_until_full": "Route to extractors and mine until cargo full (requires miner gear).",
    "deposit_to_hub": "Route to hub and deposit carried resources (requires miner gear + carried resources).",
    "explore": "Explore the map to discover new junctions, extractors, and routes.",
    "unstuck": "Execute a short escape pattern to break navigation deadlocks.",
}

_SKILL_ALIASES = {"unstick": "unstuck"}
# Issue-16: "defend" is a virtual skill for heartless aligners when hub is depleted
_ALL_VALID_SKILLS = set(CROSS_ROLE_SKILLS.keys()) | {"defend"}


def _parse_cross_role_skill(text: str) -> tuple[str | None, str]:
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
        skill = _SKILL_ALIASES.get(skill, skill)
        return (skill if skill in _ALL_VALID_SKILLS else None, "non-json response")
    if not isinstance(payload, dict):
        return None, "response was not a JSON object"
    skill = payload.get("skill")
    reason = payload.get("reason", "")
    if not isinstance(skill, str):
        return None, "missing skill field"
    skill = _SKILL_ALIASES.get(skill, skill)
    return (skill if skill in _ALL_VALID_SKILLS else None, str(reason))


_ALIGNER_SKILLS = {k: v for k, v in CROSS_ROLE_SKILLS.items() if k in {"get_heart", "align_neutral", "explore", "unstuck"}}
_MINER_SKILLS = {k: v for k, v in CROSS_ROLE_SKILLS.items() if k in {"mine_until_full", "deposit_to_hub", "explore", "unstuck"}}


def build_cross_role_prompt(
    *,
    current_gear: str,
    has_heart: bool,
    carried_resources: int,
    return_load: int,
    hub_visible: bool,
    known_hubs: int,
    known_neutral_junctions: int,
    known_friendly_junctions: int,
    known_enemy_junctions: int,
    known_extractors: int,
    current_skill: str | None,
    no_move_steps: int,
    recent_events: list[str],
    team_aligners: int = 0,
    team_miners: int = 0,
    team_size: int = 8,
    preferred_role: str = "",
    hub_depleted: bool = False,
    hub_hard_depleted: bool = False,
) -> str:
    # Select skills relevant to current gear (no gear switching via LLM)
    if current_gear == "aligner":
        if hub_depleted and not has_heart:
            # Issue-16: hub depleted or on cooldown — explore then retry
            # Don't switch to mining (deposit_to_hub has navigation issues that waste 400 steps)
            skill_set = {k: v for k, v in _ALIGNER_SKILLS.items() if k != "get_heart"}
            if hub_hard_depleted:
                role_hint = (
                    "You are in ALIGNER mode. The hub hearts are depleted. "
                    "Explore to discover new territory and junctions while waiting for opportunities."
                )
            else:
                role_hint = (
                    "You are in ALIGNER mode. Recent attempts to get a heart failed — "
                    "the hub may be temporarily empty. Explore to find new routes or junctions, "
                    "then try again soon."
                )
            preconditions = (
                "- explore: PREFERRED — discover new territory\n"
                "- get_heart is temporarily unavailable\n"
            )
        else:
            skill_set = _ALIGNER_SKILLS
            role_hint = "You are in ALIGNER mode. Your job: get hearts, then align junctions."
            preconditions = (
                "- get_heart: requires current_gear == 'aligner' AND hub accessible\n"
                "- align_neutral: requires current_gear == 'aligner' AND has_heart == true AND known_alignable_junctions > 0\n"
            )
    elif current_gear == "miner":
        skill_set = _MINER_SKILLS
        role_hint = (
            "You are in MINER mode. Your job: mine resources, then deposit to hub. "
            "After depositing, explore briefly to find new extractor types before mining again. "
            "The hub needs ALL four resource types (carbon, oxygen, germanium, silicon) to create hearts."
        )
        preconditions = (
            "- mine_until_full: requires current_gear == 'miner' AND known_extractors > 0\n"
            "- deposit_to_hub: requires current_gear == 'miner' AND carried_resources > 0\n"
            "- explore: use after depositing to discover different extractor types\n"
        )
    else:
        # No valid gear (none, scrambler, scout) — include gear_up skills so LLM can recover.
        # Scrambler/scout gear is contamination from wrong station; agent needs to navigate to
        # a gear station to acquire the correct gear.
        skill_set = {
            "gear_up_aligner": CROSS_ROLE_SKILLS["gear_up_aligner"],
            "gear_up_miner": CROSS_ROLE_SKILLS["gear_up_miner"],
            "explore": CROSS_ROLE_SKILLS["explore"],
            "unstuck": CROSS_ROLE_SKILLS["unstuck"],
        }
        if current_gear in ("scrambler", "scout"):
            if preferred_role:
                role_hint = (
                    f"You have {current_gear} gear (wrong gear — contamination). "
                    f"Your PREFERRED ROLE is {preferred_role.upper()}. "
                    f"You MUST use gear_up_{preferred_role} to restore your role. "
                    f"Do NOT switch roles."
                )
            else:
                role_hint = (
                    f"You have {current_gear} gear (wrong gear — contamination). "
                    "Navigate to the aligner or miner station to acquire the correct gear."
                )
        else:
            if preferred_role:
                role_hint = (
                    f"You have no gear yet. Your PREFERRED ROLE is {preferred_role.upper()}. "
                    f"Use gear_up_{preferred_role} to acquire your role gear."
                )
            else:
                role_hint = "You have no gear yet — explore to find a gear station, then gear up."
        preconditions = ""

    skills_text = "\n".join(f"- {name}: {desc}" for name, desc in skill_set.items())
    events_text = "\n".join(f"- {e}" for e in recent_events[-6:]) or "- none"

    return (
        f"You are a cog agent in CoGames. {role_hint}\n"
        "Your team wins by aligning and holding junctions.\n\n"
        f"Preconditions:\n{preconditions}"
        "Respond as JSON: {\"skill\": \"<skill_name>\", \"reason\": \"...\"}\n\n"
        f"Available skills:\n{skills_text}\n\n"
        f"Team state:\n"
        f"- team_aligners: {team_aligners}\n"
        f"- team_miners: {team_miners}\n"
        f"- team_size: {team_size}\n\n"
        f"Agent state:\n"
        f"- current_gear: {current_gear}\n"
        f"- has_heart: {has_heart}\n"
        f"- carried_resources: {carried_resources}\n"
        f"- return_load: {return_load}\n"
        f"- hub_visible: {hub_visible}\n"
        f"- known_hubs: {known_hubs}\n"
        f"- known_neutral_junctions: {known_neutral_junctions}\n"
        f"- known_friendly_junctions: {known_friendly_junctions}\n"
        f"- known_enemy_junctions: {known_enemy_junctions}\n"
        f"- known_extractors: {known_extractors}\n"
        f"- known_alignable_junctions: {known_neutral_junctions}\n"
        f"- hub_depleted: {hub_depleted}\n"
        f"- current_skill: {current_skill or 'none'}\n"
        f"- no_move_steps: {no_move_steps}\n"
        f"\nRecent events:\n{events_text}\n"
    )


@dataclass
class CrossRoleState:
    """Combined state for agents that can play both aligner and miner roles.

    Has all fields required by AlignerPolicyImpl AND MinerSkillImpl methods
    (duck typing approach — both can operate on this state).
    """

    # StarterCogState base fields
    wander_direction_index: int = 0
    wander_steps_remaining: int = 0
    last_mode: str = "bootstrap"

    # Map memory (shared via SharedMap)
    known_free_cells: set[Coord] = field(default_factory=set)
    blocked_cells: set[Coord] = field(default_factory=set)
    move_blocked_cells: set[Coord] = field(default_factory=set)
    known_hubs: set[Coord] = field(default_factory=set)

    # Aligner-specific structures
    known_aligner_stations: set[Coord] = field(default_factory=set)
    known_neutral_junctions: set[Coord] = field(default_factory=set)
    known_friendly_junctions: set[Coord] = field(default_factory=set)
    known_enemy_junctions: set[Coord] = field(default_factory=set)
    known_hazard_stations: set[Coord] = field(default_factory=set)
    blacklisted_junctions: set[Coord] = field(default_factory=set)
    verified_hubs: set[Coord] = field(default_factory=set)
    verified_aligner_stations: set[Coord] = field(default_factory=set)

    # Miner-specific structures
    known_miner_stations: set[Coord] = field(default_factory=set)
    known_extractors: set[Coord] = field(default_factory=set)
    depleted_extractors: set[Coord] = field(default_factory=set)
    verified_extractors: set[Coord] = field(default_factory=set)
    verified_extractors_by_element: dict[str, set[Coord]] = field(default_factory=lambda: {e: set() for e in ("carbon", "oxygen", "germanium", "silicon")})
    # Issue-16: per-element extractor locations for diverse mining
    extractors_by_element: dict[str, set[Coord]] = field(default_factory=lambda: {e: set() for e in ("carbon", "oxygen", "germanium", "silicon")})
    remembered_hub_row_from_spawn: int | None = None
    remembered_hub_col_from_spawn: int | None = None

    # Move-failure tracking
    last_pos: Coord | None = None
    last_move_target: Coord | None = None
    move_cooldowns: dict[tuple[int, int], int] = field(default_factory=dict)
    steps_since_last_move: int = 0
    contamination_avoid_cells: set[Coord] = field(default_factory=set)
    gear_contamination_count: int = 0
    _prev_gear: str = ""

    # LLM planning state
    current_skill: str | None = None
    current_reason: str = ""
    skill_steps: int = 0
    no_move_steps: int = 0
    no_progress_on_target_steps: int = 0
    recent_events: list[str] = field(default_factory=list)

    # Aligner LLM tracking
    last_has_heart: bool = False
    _prev_step_had_heart: bool = False
    last_heart_count: int = 0
    last_friendly_junctions: int = 0
    consecutive_unstuck: int = 0
    explore_start_junctions: int = 0
    align_neutral_timeouts: int = 0
    get_heart_timeouts: int = 0
    consecutive_get_heart_failures: int = 0  # Issue-16: tracks consecutive get_heart stale/stuck/timeout
    get_heart_cooldown_steps: int = 0  # Issue-16: steps remaining before get_heart is allowed again
    max_hp_seen: int = 0
    retreating: bool = False
    retreat_stuck_steps: int = 0  # Issue-36 v7: consecutive no-move steps while retreating
    steps_since_last_heart: int = 0  # Issue-36: steps since agent last acquired a heart
    last_deposit_hearts_estimate: int = 0  # Issue-36: last known hearts_crafted_estimate, to detect new hearts
    get_heart_start_count: int = 0

    # Miner LLM tracking
    last_carried_total: int = 0
    # Issue-36 v15: per-element inventory tracking for accurate deposit accounting
    last_inventory_counts: dict[str, int] = field(default_factory=lambda: {"carbon": 0, "oxygen": 0, "germanium": 0, "silicon": 0})
    explore_start_extractors: int = 0
    # Hub approach diversification
    hub_approach_rotation: int = 0

    # Gear acquisition tracking (for retry + fallback logic)
    gear_up_failures: int = 0
    gear_up_failures_total: int = 0  # Issue-34 v12: cumulative counter that never resets on contamination
    gear_up_completed: bool = False  # True once any gear_up succeeds; prevents retry after accidental gear change

    # Defend patrol cycling
    defend_station_steps: int = 0
    defend_last_junction: Coord | None = None
    defend_start_hearts_estimate: int = 0

    # Issue-34: deposit tracking for heart availability signaling
    _last_seen_deposits: int = 0

    # Gear test harness (issue-12)
    episode_step: int = 0  # incremented once per game step
    phase: int = 1  # 1 = initial gear acquisition, 2 = switched gear acquisition
    phase_preferred_gear: str = ""  # overrides preferred_initial_gear in phase 2
    phase2_hub_cleared: bool = False  # True after agent passes through hub in phase 2 (hub-first waypoint)


class CrossRolePolicyImpl(StatefulPolicyImpl[CrossRoleState]):
    """Agent that can dynamically choose aligner or miner skills based on team needs."""

    _UNSTUCK_DIRECTIONS = ("north", "east", "south", "west")

    def __init__(
        self,
        policy_env_info: PolicyEnvInterface,
        agent_id: int,
        planner: LLMMinerPlannerClient | None,
        stuck_threshold: int,
        unstuck_horizon: int,
        return_load: int,
        shared_map: SharedMap | None = None,
        preferred_initial_gear: str = "",
        phase_switch_step: int = 0,
    ) -> None:
        # Aligner impl handles aligner-specific skills (gear_up aligner station, get_heart, align_neutral)
        self._aligner = AlignerPolicyImpl(policy_env_info, agent_id, shared_map=shared_map)
        # Miner impl handles miner-specific skills (gear_up miner station, mine_until_full, deposit_to_hub)
        self._miner = MinerSkillImpl(policy_env_info, agent_id, return_load=return_load, shared_map=shared_map)
        self._planner = planner
        self._stuck_threshold = stuck_threshold
        self._unstuck_horizon = unstuck_horizon
        self._return_load = return_load
        self._shared_map = shared_map
        self._preferred_initial_gear = preferred_initial_gear
        self._phase_switch_step = phase_switch_step
        # Store hub_tags for hub visibility check
        self._hub_tags = self._aligner._starter._resolve_tag_ids(["hub"])

    def initial_agent_state(self) -> CrossRoleState:
        state = CrossRoleState()
        self._bind_shared_map(state)
        return state

    def _bind_shared_map(self, state: CrossRoleState) -> None:
        sm = self._shared_map
        if sm is None:
            return
        state.known_free_cells = sm.known_free_cells
        state.blocked_cells = sm.blocked_cells
        state.move_blocked_cells = sm.move_blocked_cells
        state.known_hubs = sm.known_hubs
        state.known_aligner_stations = sm.known_aligner_stations
        state.known_miner_stations = sm.known_miner_stations
        state.known_hazard_stations = sm.known_hazard_stations
        state.known_extractors = sm.known_extractors
        state.depleted_extractors = sm.depleted_extractors
        state.known_neutral_junctions = sm.known_neutral_junctions
        state.known_friendly_junctions = sm.known_friendly_junctions
        state.known_enemy_junctions = sm.known_enemy_junctions
        # Issue-36 v20: share per-element extractor locations across all agents
        state.extractors_by_element = sm.extractors_by_element

    def _copy_with_shared(self, state: CrossRoleState) -> CrossRoleState:
        """Return state with shared map fields re-bound (after delegate calls may have returned new state)."""
        sm = self._shared_map
        if sm is None:
            return state
        return replace(
            state,
            known_free_cells=sm.known_free_cells,
            blocked_cells=sm.blocked_cells,
            move_blocked_cells=sm.move_blocked_cells,
            known_hubs=sm.known_hubs,
            known_aligner_stations=sm.known_aligner_stations,
            known_miner_stations=sm.known_miner_stations,
            known_hazard_stations=sm.known_hazard_stations,
            known_extractors=sm.known_extractors,
            depleted_extractors=sm.depleted_extractors,
            known_neutral_junctions=sm.known_neutral_junctions,
            known_friendly_junctions=sm.known_friendly_junctions,
            known_enemy_junctions=sm.known_enemy_junctions,
            extractors_by_element=sm.extractors_by_element,
        )

    def _event(self, state: CrossRoleState, message: str) -> None:
        state.recent_events.append(message)
        del state.recent_events[:-10]

    def _current_gear(self, obs: AgentObservation) -> str:
        gear = self._aligner._current_gear(obs)
        return gear if gear else "none"

    def _inventory_count(self, obs: AgentObservation, item: str) -> int:
        return self._aligner._inventory_count(obs, item)

    def _carried_total(self, obs: AgentObservation) -> int:
        return self._miner._carried_total(obs)

    def _feature_value(self, obs: AgentObservation, feature_name: str) -> int | None:
        for token in obs.tokens:
            if token.feature.name == feature_name:
                return int(token.value)
        return None

    def _hub_visible(self, obs: AgentObservation) -> bool:
        return self._aligner._starter._closest_tag_location(obs, self._hub_tags) is not None

    def _current_abs(self, obs: AgentObservation) -> Coord:
        return self._aligner._spawn_offset(obs)

    def _known_alignable_junctions(self, state: CrossRoleState) -> set[Coord]:
        return {j for j in state.known_neutral_junctions - state.blacklisted_junctions
                if self._aligner._is_alignable(j, state)}

    def _dist_to_nearest_safe(self, current_abs: Coord, state: CrossRoleState) -> int:
        min_dist = 9999
        for hub in state.known_hubs:
            d = abs(current_abs[0] - hub[0]) + abs(current_abs[1] - hub[1])
            if d < min_dist:
                min_dist = d
        for fj in state.known_friendly_junctions:
            d = abs(current_abs[0] - fj[0]) + abs(current_abs[1] - fj[1])
            if d < min_dist:
                min_dist = d
        return min_dist

    def _update_map_memory(self, obs: AgentObservation, state: CrossRoleState) -> Coord:
        """Update map from both aligner and miner perspectives."""
        # Use aligner map memory (handles junctions, aligner stations, hazards)
        current_abs = self._aligner._update_map_memory(obs, state)
        # Save movement tracking state — aligner already processed it correctly.
        # Without this, the miner call re-increments steps_since_last_move (always >=1
        # after a move, doubles when stuck) and double-ticks cooldowns (expire 2x fast).
        saved_last_pos = state.last_pos
        saved_last_move_target = state.last_move_target
        saved_steps_since = state.steps_since_last_move
        saved_cooldowns = dict(state.move_cooldowns)
        # Additionally update miner-specific structures (extractors, miner stations)
        # We reuse the miner's _update_map_memory but pass our CrossRoleState (duck typing)
        self._miner._update_map_memory(obs, state)
        # Restore movement tracking — prevent double counting
        state.last_pos = saved_last_pos
        state.last_move_target = saved_last_move_target
        state.steps_since_last_move = saved_steps_since
        state.move_cooldowns = saved_cooldowns
        # Issue-36 v13: miner update clears+rebuilds blocked_cells from its own blocked_now,
        # which doesn't include aligner stations. Visible aligner stations get unblocked and
        # added to known_free_cells. Fix: re-apply blocking for all known aligner stations.
        if state.known_aligner_stations:
            state.blocked_cells.update(state.known_aligner_stations)
            state.known_free_cells.difference_update(state.known_aligner_stations)
        # Issue-35: Track agent positions and gear for congestion avoidance + team coordination
        if self._shared_map is not None:
            self._shared_map.agent_positions[obs.agent_id] = current_abs
            gear = self._current_gear(obs)
            if gear:
                self._shared_map.agent_gears[obs.agent_id] = gear
            if state.current_skill != "align_neutral":
                self._shared_map.aligner_targets.pop(obs.agent_id, None)
            if state.current_skill != "get_heart":
                self._shared_map.agents_getting_hearts.discard(obs.agent_id)
            if state.current_skill != "mine_until_full" and hasattr(self._shared_map, 'miner_targets'):
                self._shared_map.miner_targets.pop(obs.agent_id, None)
        return current_abs

    def _update_progress(self, obs: AgentObservation, state: CrossRoleState) -> None:
        has_heart = self._inventory_count(obs, "heart") > 0
        friendly_count = len(state.known_friendly_junctions)
        carried_total = self._carried_total(obs)
        current_abs = self._current_abs(obs)

        heart_count = self._inventory_count(obs, "heart")
        if state.current_skill == "get_heart" and heart_count > state.last_heart_count:
            self._event(state, f"heart count increased to {heart_count}")
        if state.current_skill == "align_neutral" and friendly_count > state.last_friendly_junctions:
            self._event(state, f"friendly junction count increased {state.last_friendly_junctions}→{friendly_count}")
        if state.current_skill == "deposit_to_hub" and carried_total < state.last_carried_total:
            self._event(state, f"deposited cargo {state.last_carried_total}→{carried_total}")
        if state.current_skill == "mine_until_full" and carried_total > state.last_carried_total:
            self._event(state, f"cargo increased {state.last_carried_total}→{carried_total}")

        # Issue-36: track steps since last heart acquisition for periodic hub return
        if has_heart and not state.last_has_heart:
            state.steps_since_last_heart = 0
        else:
            state.steps_since_last_heart += 1

        # Issue-36 v7: decrement get_heart cooldown every step (was only in _plan_skill).
        # Bug: cooldown only counted down during replanning, not while exploring.
        # With max cooldown of 8 and explore taking 200+ steps, cooldown was effectively frozen.
        if state.get_heart_cooldown_steps > 0:
            state.get_heart_cooldown_steps -= 1

        # Issue-36: track deposit events for heart pipeline awareness
        # Issue-36 v7: track ANY deposit (not just during deposit_to_hub skill).
        # Emergency deposits during retreat and auto-deposits near hub should also be counted.
        # Issue-36 v15: use per-element inventory tracking for accurate deposit accounting.
        # Previously approximated by distributing evenly, which misreported when miners
        # carried unbalanced loads (e.g., 15 carbon + 5 oxygen → reported as 5 each).
        gear = self._current_gear(obs)
        current_inv = self._miner._inventory_counts(obs) if gear == "miner" else {}
        if gear == "miner" and carried_total < state.last_carried_total:
            near_deposit = any(
                abs(current_abs[0] - h[0]) + abs(current_abs[1] - h[1]) <= 2
                for h in state.known_hubs
            )
            if not near_deposit and self._shared_map is not None:
                near_deposit = any(
                    abs(current_abs[0] - j[0]) + abs(current_abs[1] - j[1]) <= 1
                    for j in self._shared_map.known_friendly_junctions
                )
            if near_deposit and self._shared_map is not None:
                for elem in ("carbon", "oxygen", "germanium", "silicon"):
                    prev = state.last_inventory_counts.get(elem, 0)
                    curr = current_inv.get(elem, 0)
                    deposited_elem = max(0, prev - curr)
                    if deposited_elem > 0:
                        self._shared_map.total_deposits[elem] += deposited_elem
                # Estimate hearts that could have been crafted from all deposits
                min_deposits = min(self._shared_map.total_deposits.values())
                new_estimate = min_deposits // 7  # 7 of each element per heart
                if new_estimate > self._shared_map.hearts_crafted_estimate:
                    self._shared_map.hearts_crafted_estimate = new_estimate
                    logger.info(
                        "agent=%s hearts_crafted_estimate=%d deposits=%s",
                        obs.agent_id, new_estimate, self._shared_map.total_deposits,
                    )

        last_action_move = self._feature_value(obs, "last_action_move")
        gear = self._current_gear(obs)

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
        active_ext = state.known_extractors - state.depleted_extractors
        near_extractor = any(
            abs(current_abs[0] - e[0]) + abs(current_abs[1] - e[1]) <= 1
            for e in active_ext
        )

        made_progress = (
            (state.current_skill == "get_heart" and heart_count > state.last_heart_count)
            or (state.current_skill == "align_neutral" and friendly_count > state.last_friendly_junctions)
            or (state.current_skill == "gear_up_aligner" and gear == "aligner")
            or (state.current_skill == "gear_up_miner" and gear == "miner")
            or (state.current_skill == "deposit_to_hub" and carried_total < state.last_carried_total)
            or (state.current_skill == "mine_until_full" and carried_total > state.last_carried_total)
        )
        state._prev_step_had_heart = state.last_has_heart
        state.last_has_heart = has_heart
        state.last_heart_count = heart_count
        state.last_friendly_junctions = friendly_count
        state.last_carried_total = carried_total
        if gear == "miner":
            state.last_inventory_counts = {e: current_inv.get(e, 0) for e in ("carbon", "oxygen", "germanium", "silicon")}
        stationary_on_valid_target = (
            (state.current_skill == "get_heart" and near_hub)
            or (state.current_skill == "align_neutral" and current_abs in self._known_alignable_junctions(state))
            or (state.current_skill == "gear_up_aligner" and near_aligner_station)
            or (state.current_skill == "gear_up_miner" and near_miner_station)
            or (state.current_skill == "mine_until_full" and near_extractor)  # v12: was near_hub (bug)
            or (state.current_skill == "deposit_to_hub" and (near_hub or any(
                abs(current_abs[0] - j[0]) + abs(current_abs[1] - j[1]) <= 1
                for j in state.known_friendly_junctions)))
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

    def _team_gear_counts(self) -> tuple[int, int]:
        """Return (num_aligners, num_miners) across the team from shared map."""
        sm = self._shared_map
        if sm is None or not hasattr(sm, "agent_gears"):
            return 0, 0
        gears = sm.agent_gears.values()
        return sum(1 for g in gears if g == "aligner"), sum(1 for g in gears if g == "miner")

    def _clear_shared_map_tracking(self, agent_id: int) -> None:
        """Issue-36 v19: clean up SharedMap coordination state for this agent.

        Called when an agent's skill is cancelled externally (retreat, phase switch,
        tether) without going through _plan_skill. Without this, the agent stays
        registered in heart queue / aligner targets during retreat, blocking teammates.
        """
        if self._shared_map is not None:
            self._shared_map.agents_getting_hearts.discard(agent_id)
            self._shared_map.aligner_targets.pop(agent_id, None)

    def _set_skill_fast(self, obs: AgentObservation, state: CrossRoleState, skill: str, reason: str) -> None:
        """Issue-36 v18: centralized fast-path skill assignment with SharedMap cleanup.

        All fast-path returns in _plan_skill use this to ensure heart queue and
        aligner target tracking stay consistent.
        """
        # Clean up SharedMap tracking from previous skill and register for new skill
        if self._shared_map is not None:
            if skill == "get_heart":
                self._shared_map.agents_getting_hearts.add(obs.agent_id)
            else:
                self._shared_map.agents_getting_hearts.discard(obs.agent_id)
            if skill != "align_neutral":
                self._shared_map.aligner_targets.pop(obs.agent_id, None)

        state.current_skill = skill
        state.current_reason = reason
        state.skill_steps = 0
        state.no_move_steps = 0
        state.no_progress_on_target_steps = 0
        state.defend_station_steps = 0
        state.defend_last_junction = None
        if skill in {"explore", "gear_up_aligner", "gear_up_miner"}:
            state.explore_start_junctions = len(state.known_neutral_junctions) + len(state.known_enemy_junctions) + len(state.known_friendly_junctions)
            state.explore_start_extractors = len(state.known_extractors) + len(state.depleted_extractors)
        if skill == "defend" and self._shared_map is not None:
            state.defend_start_hearts_estimate = self._shared_map.hearts_crafted_estimate
        if skill == "get_heart":
            state.get_heart_start_count = self._inventory_count(obs, "heart")
        self._event(state, f"planner selected {skill}: {reason}")

    def _plan_skill(self, obs: AgentObservation, state: CrossRoleState) -> None:
        gear = self._current_gear(obs)
        has_heart = self._inventory_count(obs, "heart") > 0
        carried = self._carried_total(obs)
        known_alignable = self._known_alignable_junctions(state)

        # Update shared gear tracking
        if self._shared_map is not None and hasattr(self._shared_map, "agent_gears"):
            self._shared_map.agent_gears[obs.agent_id] = gear

        # Effective preferred gear: phase_preferred_gear (set at phase switch) or original preference
        effective_preferred = state.phase_preferred_gear or self._preferred_initial_gear

        # Bootstrap: acquire preferred gear.
        # Phase 1: fire when gear=="none" and gear_up_completed==False (initial acquisition)
        # Phase 2: fire when gear!=effective_preferred and gear_up_completed==False (gear switch)
        # v17: LLM prompt includes gear_up_aligner/miner for scrambler/scout so agents can
        # self-correct without bootstrap (but bootstrap is faster and more reliable).
        # v12 fix: scout/scrambler contamination always triggers re-gear, even after gear_up_completed.
        # Bug: agent 3 (seed 44) completed gear_up_miner successfully, then contaminated during
        # mine_until_full (walked through scout station). gear_up_completed=True blocked re-bootstrap.
        contaminated = gear in ("scrambler", "scout")
        if gear == "none" and state.gear_up_completed:
            state.gear_up_completed = False
            state.gear_up_failures = 0
            logger.info("agent=%s death_detected: gear=none but gear_up_completed=True, resetting for re-gear", obs.agent_id)
            self._event(state, "death detected: resetting gear_up state for re-acquisition")
        needs_gear_up = effective_preferred and (
            contaminated  # always re-gear on contamination, even if gear_up previously completed
            or (
                not state.gear_up_completed
                and (
                    gear == "none"
                    or (state.phase == 2 and gear != effective_preferred and gear in ("aligner", "miner"))
                )
            )
        )
        if contaminated and state.gear_up_completed:
            # Reset so bootstrap retries from scratch; contamination invalidates completed status
            state.gear_up_completed = False
            state.gear_up_failures = 0
            self._event(state, f"contamination detected ({gear}): resetting gear_up state for re-acquisition")
        if needs_gear_up:
            if (
                gear not in ("miner",)
                and not has_heart
                and effective_preferred == "aligner"
                and state.known_hubs
                and not contaminated
            ):
                current_abs = self._current_abs(obs)
                near_hub = any(
                    abs(current_abs[0] - h[0]) + abs(current_abs[1] - h[1]) <= 2
                    for h in state.known_hubs
                )
                if near_hub:
                    self._set_skill_fast(obs, state, "get_heart",
                        "heart-before-gear: grabbing heart near hub before aligner gear-up")
                    return
            failures = state.gear_up_failures
            if failures == 0:
                bootstrap_gear = effective_preferred
                reason = f"phase{state.phase} gear target: {bootstrap_gear} (attempt 1)"
            elif effective_preferred == "aligner":
                # Issue-34 v7: Designated aligners persist retrying aligner gear.
                # Issue-34 v12: But after 10 TOTAL failures (across contamination resets),
                # the aligner station is likely permanently unreachable.
                # Convert to miner to reclaim the agent as a productive miner.
                # Use gear_up_failures_total (never resets) instead of gear_up_failures
                # (resets on contamination, which happens during hazard-bypass navigation).
                if state.gear_up_failures_total >= 10:
                    bootstrap_gear = "miner"
                    state.phase_preferred_gear = "miner"
                    reason = f"phase{state.phase} aligner->miner conversion: {state.gear_up_failures_total} total gear_up failures, station unreachable"
                    logger.info("agent=%s gear_up_failure_ceiling: converting aligner->miner after %d total failures", obs.agent_id, state.gear_up_failures_total)
                else:
                    bootstrap_gear = "aligner"
                    reason = f"phase{state.phase} persistent aligner retry (attempt {failures + 1}, failures={failures})"
            elif failures == 1:
                bootstrap_gear = "miner" if effective_preferred == "aligner" else "aligner"
                reason = f"phase{state.phase} fallback gear: {bootstrap_gear} (preferred {effective_preferred} failed)"
            elif state.phase == 2:
                # v7: in phase 2, keep retrying the preferred gear after 2+ failures
                bootstrap_gear = effective_preferred
                reason = f"phase2 persistent retry: {bootstrap_gear} (attempt {failures + 1}, failures={failures})"
            else:
                # Issue-36 v6: after 4+ failures, explore near hub instead of infinite gear_up retries.
                # The gear_up navigation is failing (stale after 20 steps), so wandering near hub
                # is safer (territory healing) and may walk through the correct gear station.
                if contaminated and failures >= 4:
                    logger.info("agent=%s issue36_contamination_explore: failures=%d gear=%s", obs.agent_id, failures, gear)
                    self._set_skill_fast(obs, state, "explore",
                        f"contamination recovery: explore near hub after {failures} gear_up failures")
                    return
                bootstrap_gear = effective_preferred  # Phase 1 with 2-3 failures: keep trying preferred
                reason = f"phase{state.phase} persistent retry: {bootstrap_gear} (attempt {failures + 1}, failures={failures})"

            if bootstrap_gear:
                skill = f"gear_up_{bootstrap_gear}"
                logger.info("agent=%s bootstrap_skill=%s failures=%d phase=%d", obs.agent_id, skill, failures, state.phase)
                if skill in CROSS_ROLE_SKILLS:
                    self._set_skill_fast(obs, state, skill, reason)
                    return

        team_aligners, team_miners = self._team_gear_counts()
        team_size = max(1, len(self._shared_map.agent_gears) if self._shared_map and hasattr(self._shared_map, "agent_gears") else 8)

        # Issue-16: hub depletion awareness
        # Only use cooldown-based blocking (no hard block). After cooldown expires,
        # agents retry get_heart. If make_heart created new hearts from deposited
        # resources, the retry succeeds. If not, failure sets a new cooldown.
        # Note: cooldown is decremented in _update_progress (every step), not here.
        hub_hearts_used = self._shared_map.hub_hearts_withdrawn if self._shared_map else 0
        hub_deposits_total = self._shared_map.hub_deposits_total if self._shared_map and hasattr(self._shared_map, 'hub_deposits_total') else 0
        if hasattr(state, '_last_seen_deposits') and hub_deposits_total > state._last_seen_deposits:
            # New deposits arrived — reset cooldown so aligner retries get_heart
            state.consecutive_get_heart_failures = 0
            state.get_heart_cooldown_steps = 0
        state._last_seen_deposits = hub_deposits_total
        hub_hard_depleted = False  # v13: removed hard block to allow make_heart retries
        hub_on_cooldown = state.get_heart_cooldown_steps > 0

        # Issue-36: deposit-aware cooldown reset
        # When team deposits suggest make_heart has created new hearts,
        # immediately reset cooldown so aligners return to collect them.
        if self._shared_map is not None and hub_on_cooldown:
            estimated_hearts = self._shared_map.hearts_crafted_estimate
            hearts_consumed = self._shared_map.hub_hearts_withdrawn
            # If estimated crafted hearts exceed what's been withdrawn (minus initial 5),
            # there should be hearts available in the hub
            hearts_from_crafting_consumed = max(0, hearts_consumed - 8)  # 5 initial hearts + 3 from initial elements
            if estimated_hearts > hearts_from_crafting_consumed:
                state.get_heart_cooldown_steps = 0
                state.consecutive_get_heart_failures = 0
                hub_on_cooldown = False
                logger.info(
                    "agent=%s issue36_cooldown_reset: estimated_crafted=%d consumed_crafted=%d",
                    obs.agent_id, estimated_hearts, hearts_from_crafting_consumed,
                )
                self._event(state, f"hub cooldown reset: deposits suggest {estimated_hearts - hearts_from_crafting_consumed} hearts available")

        # Issue-36: periodic hub return for aligners without hearts
        # After 200 steps without a heart, force aligner to try get_heart regardless of cooldown
        # This prevents the explore drift where agents wander away from hub forever
        _HUB_RETURN_INTERVAL = 200
        if (
            gear == "aligner"
            and not has_heart
            and hub_on_cooldown
            and state.steps_since_last_heart >= _HUB_RETURN_INTERVAL
            and state.known_hubs
        ):
            state.get_heart_cooldown_steps = 0
            state.consecutive_get_heart_failures = 0
            hub_on_cooldown = False
            state.steps_since_last_heart = 0  # reset to prevent immediate re-trigger
            logger.info(
                "agent=%s issue36_periodic_hub_return after %d steps without heart",
                obs.agent_id, _HUB_RETURN_INTERVAL,
            )
            self._event(state, f"periodic hub return after {_HUB_RETURN_INTERVAL} steps without heart")

        hub_depleted = hub_on_cooldown

        # Issue-36: fast-path for aligner heart acquisition and alignment
        # Skip LLM call when the optimal action is obvious. This saves ~2 seconds
        # per decision, which is critical at 10k steps where throughput matters.
        if gear == "aligner":
            if has_heart and known_alignable:
                self._set_skill_fast(obs, state, "align_neutral",
                    f"fast-path: have heart and {len(known_alignable)} alignable targets")
                return
            if not has_heart and not hub_depleted and state.known_hubs:
                if state.get_heart_timeouts >= 1 and state.known_friendly_junctions:
                    self._set_skill_fast(obs, state, "defend",
                        f"fast-path: defend after {state.get_heart_timeouts} get_heart timeout(s)")
                    return
                if self._shared_map is not None:
                    _INITIAL_ELEMENT_HEARTS = 3  # 24 initial elements // 7 heart_cost
                    estimated_available = max(0,
                        5 + _INITIAL_ELEMENT_HEARTS + self._shared_map.hearts_crafted_estimate - self._shared_map.hub_hearts_withdrawn
                    )
                    others_getting = len(self._shared_map.agents_getting_hearts - {obs.agent_id})
                    if others_getting >= max(1, estimated_available):
                        if len(state.known_friendly_junctions) >= 3:
                            self._set_skill_fast(obs, state, "defend",
                                f"fast-path: heart queue full ({others_getting} in flight, ~{estimated_available} available), defending")
                        else:
                            self._set_skill_fast(obs, state, "explore",
                                f"fast-path: heart queue full ({others_getting} in flight, ~{estimated_available} available)")
                        return
                logger.info("agent=%s issue36_fast_path: skipping LLM, selecting get_heart directly", obs.agent_id)
                self._set_skill_fast(obs, state, "get_heart",
                    "fast-path: aligner needs heart, hub not on cooldown")
                return
            # Issue-36 v7: fast-path for remaining aligner states (eliminates more LLM calls)
            if has_heart and not known_alignable:
                fj_count = len(state.known_friendly_junctions)
                late_game = state.episode_step > 5000
                enemy_active = bool(state.known_enemy_junctions)
                substantial = fj_count >= 20 and state.episode_step > 3000
                if fj_count >= 5 and (late_game or enemy_active or substantial):
                    trigger = "late-game" if late_game else ("enemy-active" if enemy_active else "substantial-territory")
                    self._set_skill_fast(obs, state, "defend",
                        f"fast-path: {trigger} patrol ({fj_count} friendly, step={state.episode_step})")
                else:
                    self._set_skill_fast(obs, state, "explore",
                        "fast-path: aligner has heart but no alignable junctions, exploring")
                return
            if not has_heart and hub_depleted:
                self._set_skill_fast(obs, state, "explore",
                    f"fast-path: no heart, hub on cooldown (cd={state.get_heart_cooldown_steps})")
                return
        elif gear == "miner":
            if carried >= self._return_load:
                self._set_skill_fast(obs, state, "deposit_to_hub",
                    f"fast-path: cargo full ({carried}/{self._return_load})")
                return
            active_extractors = state.known_extractors - state.depleted_extractors
            if active_extractors and carried < self._return_load:
                self._set_skill_fast(obs, state, "mine_until_full",
                    f"fast-path: have {len(active_extractors)} active extractors, cargo {carried}/{self._return_load}")
                return
            if not active_extractors and carried < self._return_load:
                self._set_skill_fast(obs, state, "explore",
                    "fast-path: miner has no active extractors, exploring to discover some")
                return

        # Skip LLM call when planner is None (scripted_miners mode)
        text = ""
        if self._planner is not None:
            prompt = build_cross_role_prompt(
                current_gear=gear,
                has_heart=has_heart,
                carried_resources=carried,
                return_load=self._return_load,
                hub_visible=self._hub_visible(obs),
                known_hubs=len(state.known_hubs),
                known_neutral_junctions=len(state.known_neutral_junctions),
                known_friendly_junctions=len(state.known_friendly_junctions),
                known_enemy_junctions=len(state.known_enemy_junctions),
                known_extractors=len(state.known_extractors - state.depleted_extractors),
                current_skill=state.current_skill,
                no_move_steps=state.no_move_steps,
                recent_events=state.recent_events,
                team_aligners=team_aligners,
                team_miners=team_miners,
                team_size=team_size,
                preferred_role=state.phase_preferred_gear or self._preferred_initial_gear,
                hub_depleted=hub_depleted,
                hub_hard_depleted=hub_hard_depleted,
            )
            logger.info("agent=%s cross_role_prompt=%s", obs.agent_id, prompt.replace("\n", " | "))
            started_at = time.perf_counter()
            try:
                text = self._planner.complete(prompt)
            except Exception as exc:
                latency_ms = (time.perf_counter() - started_at) * 1000.0
                logger.warning("agent=%s cross_role_llm_error_ms=%.1f error=%s", obs.agent_id, latency_ms, exc)
            else:
                latency_ms = (time.perf_counter() - started_at) * 1000.0
            logger.info(
                "agent=%s cross_role_response_ms=%.1f response=%s",
                obs.agent_id, latency_ms, text.replace("\n", " "),
            )
        else:
            logger.info("agent=%s cross_role_scripted_only (no planner)", obs.agent_id)
        skill, reason = _parse_cross_role_skill(text)
        was_stuck = bool(
            state.recent_events and (
                "exited as stuck" in state.recent_events[-1]
                or "timed out after" in state.recent_events[-1]
            )
        )
        was_stale = bool(
            state.recent_events and "exited as stale" in state.recent_events[-1]
        )

        # Scripted fallback if LLM returns invalid skill
        if skill is None:
            if gear == "none":
                if was_stuck or was_stale:
                    skill = "explore"
                else:
                    active_ext_count = len(state.known_extractors - state.depleted_extractors)
                    skill = "gear_up_aligner" if len(known_alignable) >= active_ext_count else "gear_up_miner"
            elif gear == "aligner":
                if was_stuck or was_stale:
                    skill = "explore"
                elif not has_heart and state.known_hubs:
                    skill = "get_heart"
                elif has_heart and known_alignable:
                    skill = "align_neutral"
                else:
                    skill = "explore"
            elif gear == "miner":
                if carried >= self._return_load:
                    if was_stuck:
                        skill = "explore"
                    else:
                        skill = "deposit_to_hub"
                elif was_stale:
                    skill = "explore"
                elif was_stuck:
                    skill = "explore"
                elif state.known_extractors - state.depleted_extractors:
                    skill = "mine_until_full"
                else:
                    skill = "explore"
            else:
                skill = "explore"
            reason = f"scripted fallback ({reason})"

        # Precondition enforcement
        # Issue-16: prevent get_heart when hub depleted or on cooldown
        if skill == "get_heart" and hub_depleted and not has_heart:
            skill = "explore"
            reason = f"overrode get_heart to explore: hub={'depleted' if hub_hard_depleted else 'cooldown'} (used={hub_hearts_used}, failures={state.consecutive_get_heart_failures}, cd={state.get_heart_cooldown_steps})"
            logger.info("agent=%s hub_depletion_override: skill=explore hearts_used=%d failures=%d cooldown=%d", obs.agent_id, hub_hearts_used, state.consecutive_get_heart_failures, state.get_heart_cooldown_steps)
        # Must have correct gear for role-specific skills
        if skill == "get_heart" and gear != "aligner":
            skill = "gear_up_aligner"
            reason = f"overrode to gear_up_aligner: need aligner gear for get_heart (current={gear})"
        if skill == "align_neutral" and gear != "aligner":
            skill = "gear_up_aligner"
            reason = f"overrode to gear_up_aligner: need aligner gear for align_neutral"
        if skill == "align_neutral" and gear == "aligner" and not has_heart:
            if hub_depleted:
                skill = "explore"
                reason = "overrode align_neutral to explore: no heart and hub depleted/cooldown"
            else:
                skill = "get_heart"
                reason = "overrode to get_heart: need heart for align_neutral"
        if skill == "align_neutral" and gear == "aligner" and has_heart and not known_alignable:
            skill = "explore"
            reason = "overrode to explore: no alignable junctions known"
        # Issue-16: prioritize alignment when agent has heart and targets exist
        if gear == "aligner" and has_heart and known_alignable and skill in {"explore", "get_heart"}:
            skill = "align_neutral"
            reason = f"overrode {skill} to align_neutral: have heart and {len(known_alignable)} alignable targets"
        if skill == "mine_until_full" and gear != "miner":
            skill = "gear_up_miner"
            reason = f"overrode to gear_up_miner: need miner gear for mining (current={gear})"
        # Issue-36: prevent mine_until_full with no known extractors — wastes 400 steps on predicted positions
        if skill == "mine_until_full" and gear == "miner" and not (state.known_extractors - state.depleted_extractors):
            skill = "explore"
            reason = "overrode mine_until_full to explore: no known extractors (discover some first)"
        if skill == "deposit_to_hub" and gear != "miner":
            skill = "gear_up_miner"
            reason = f"overrode to gear_up_miner: need miner gear for deposit (current={gear})"
        if skill == "deposit_to_hub" and gear == "miner" and carried == 0:
            skill = "mine_until_full" if (state.known_extractors - state.depleted_extractors) else "explore"
            reason = "overrode to mine: no cargo to deposit"
        if skill == "gear_up_aligner" and gear == "aligner":
            if has_heart and known_alignable:
                skill = "align_neutral"
                reason = "overrode: already have aligner gear, have heart and target"
            elif not has_heart and hub_depleted:
                skill = "explore"
                reason = "overrode: already have aligner gear, hub depleted/cooldown → explore"
            elif not has_heart and state.known_hubs:
                skill = "get_heart"
                reason = "overrode: already have aligner gear, need heart"
            else:
                skill = "explore"
                reason = "overrode: already have aligner gear"
        if skill == "gear_up_miner" and gear == "miner":
            if carried >= self._return_load:
                skill = "deposit_to_hub"
                reason = "overrode: already have miner gear, cargo full"
            elif state.known_extractors - state.depleted_extractors:
                skill = "mine_until_full"
                reason = "overrode: already have miner gear"
            else:
                skill = "explore"
                reason = "overrode: already have miner gear, no extractors"

        if gear == "aligner" and not has_heart and skill == "get_heart" and state.get_heart_timeouts >= 1 and state.known_friendly_junctions:
            skill = "defend"
            reason = f"overrode get_heart to defend after {state.get_heart_timeouts} timeout(s) (hub likely empty)"
        # Prevent consecutive unstuck loops
        if skill == "unstuck":
            state.consecutive_unstuck += 1
        else:
            state.consecutive_unstuck = 0
        if state.consecutive_unstuck >= 2 and skill == "unstuck":
            skill = "explore"
            reason = f"overrode unstuck to explore after {state.consecutive_unstuck} consecutive unstuck"
            state.consecutive_unstuck = 0

        # Issue-36 v16: clear aligner target when switching skills
        if self._shared_map is not None and skill != "align_neutral":
            self._shared_map.aligner_targets.pop(obs.agent_id, None)
        # Issue-36 v18: update heart queue — add when starting get_heart, remove otherwise
        if self._shared_map is not None:
            if skill == "get_heart":
                self._shared_map.agents_getting_hearts.add(obs.agent_id)
            else:
                self._shared_map.agents_getting_hearts.discard(obs.agent_id)

        state.current_skill = skill
        state.current_reason = reason
        state.skill_steps = 0
        state.no_move_steps = 0
        state.no_progress_on_target_steps = 0
        state.defend_station_steps = 0
        state.defend_last_junction = None
        if skill in {"explore", "gear_up_aligner", "gear_up_miner"}:
            state.explore_start_junctions = len(state.known_neutral_junctions) + len(state.known_enemy_junctions) + len(state.known_friendly_junctions)
            state.explore_start_extractors = len(state.known_extractors) + len(state.depleted_extractors)
        if skill == "defend" and self._shared_map is not None:
            state.defend_start_hearts_estimate = self._shared_map.hearts_crafted_estimate
        if skill == "get_heart":
            state.get_heart_start_count = self._inventory_count(obs, "heart")
        self._event(state, f"planner selected {skill}: {reason}")

    def _maybe_finish_skill(self, obs: AgentObservation, state: CrossRoleState) -> None:
        gear = self._current_gear(obs)
        has_heart = self._inventory_count(obs, "heart") > 0
        carried = self._carried_total(obs)
        friendly_count = len(state.known_friendly_junctions)

        effective_preferred = state.phase_preferred_gear or self._preferred_initial_gear
        if state.current_skill == "gear_up_aligner" and gear == "aligner" and state.skill_steps > 0:
            if effective_preferred == "aligner":
                self._event(state, "gear_up_aligner completed")
                state.gear_up_completed = True
            else:
                # v7/v9: completed with wrong gear (agent already had aligner, effective_preferred=miner).
                # Don't mark gear_up_completed=True (that would stop bootstrap retries).
                # Increment failures to avoid infinite loop at this fallback gear.
                state.gear_up_failures += 1
                self._event(state, f"gear_up_aligner wrong-gear completion (preferred={effective_preferred}), failures={state.gear_up_failures}")
            state.current_skill = None
        elif state.current_skill == "gear_up_miner" and gear == "miner" and state.skill_steps > 0:
            if effective_preferred == "miner":
                self._event(state, "gear_up_miner completed")
                state.gear_up_completed = True
            else:
                # v7/v9: completed with wrong gear (agent already had miner, effective_preferred=aligner).
                state.gear_up_failures += 1
                self._event(state, f"gear_up_miner wrong-gear completion (preferred={effective_preferred}), failures={state.gear_up_failures}")
            state.current_skill = None
        elif state.current_skill == "get_heart" and has_heart and state.skill_steps > 0:
            heart_count = self._inventory_count(obs, "heart")
            current_abs = self._current_abs(obs)
            near_hub = any(
                abs(current_abs[0] - h[0]) + abs(current_abs[1] - h[1]) <= 2
                for h in state.known_hubs
            )
            alignable_count = len(self._known_alignable_junctions(state))
            accumulation_target = min(5, max(3, alignable_count))
            if heart_count < accumulation_target and near_hub and state.no_progress_on_target_steps < 3:
                pass
            else:
                newly_withdrawn = max(1, heart_count - state.get_heart_start_count)
                self._event(state, f"get_heart completed: acquired {newly_withdrawn} heart(s) (now {heart_count})")
                state.get_heart_timeouts = 0
                state.consecutive_get_heart_failures = 0
                if self._shared_map is not None:
                    self._shared_map.hub_hearts_withdrawn += newly_withdrawn
                    self._shared_map.agents_getting_hearts.discard(obs.agent_id)
                    logger.info("agent=%s hub_hearts_withdrawn=%d (+%d)", obs.agent_id, self._shared_map.hub_hearts_withdrawn, newly_withdrawn)
                state.current_skill = None
        elif state.current_skill == "get_heart" and gear not in ("aligner", "none") and state.skill_steps > 0:
            self._event(state, f"get_heart aborted: gear contaminated to {gear}")
            if self._shared_map is not None:
                self._shared_map.agents_getting_hearts.discard(obs.agent_id)
            state.current_skill = None
        elif state.current_skill == "align_neutral" and gear != "aligner" and state.skill_steps > 0:
            self._event(state, f"align_neutral aborted: lost aligner gear (now {gear})")
            state.current_skill = None
        elif state.current_skill == "align_neutral" and not has_heart and state.skill_steps > 0:
            self._event(state, "align_neutral completed: heart spent")
            state.align_neutral_timeouts = 0
            state.current_skill = None
        elif state.current_skill in {"mine_until_full", "deposit_to_hub"} and gear != "miner" and state.skill_steps > 0:
            current_abs = self._current_abs(obs)
            if gear in ("scrambler", "scout"):
                state.contamination_avoid_cells.add(current_abs)
                state.gear_contamination_count += 1
            self._event(state, f"{state.current_skill} aborted: lost miner gear at {current_abs} (contamination count={state.gear_contamination_count})")
            state.current_skill = None
        elif state.current_skill == "mine_until_full" and carried >= self._return_load:
            self._event(state, f"mine_until_full completed: cargo={carried}")
            state.current_skill = None
        elif state.current_skill == "deposit_to_hub" and carried == 0:
            self._event(state, "deposit_to_hub completed")
            # Issue-34: track deposits to signal aligners when new hearts may be available
            if self._shared_map is not None:
                self._shared_map.hub_deposits_total += 1
                logger.info("agent=%s hub_deposits_total=%d", obs.agent_id, self._shared_map.hub_deposits_total)
            state.current_skill = None
        elif state.current_skill == "explore" and (
            # Issue-36 v17: miners should only complete explore on extractor discovery,
            # not junction discovery. Junction discoveries come from aligner teammates
            # via SharedMap and interrupt miner exploration prematurely — the miner
            # replans to mine_until_full and heads to a known extractor instead of
            # continuing to discover new extractor types.
            (gear != "miner" and (len(state.known_neutral_junctions) + len(state.known_enemy_junctions) + len(state.known_friendly_junctions)) > state.explore_start_junctions)
            or (len(state.known_extractors) + len(state.depleted_extractors)) > state.explore_start_extractors
        ):
            new_junctions = (len(state.known_neutral_junctions) + len(state.known_enemy_junctions) + len(state.known_friendly_junctions)) - state.explore_start_junctions
            new_extractors = (len(state.known_extractors) + len(state.depleted_extractors)) - state.explore_start_extractors
            self._event(state, f"explore completed: +{new_junctions} junctions, +{new_extractors} extractors")
            # Issue-36 v6: reset gear_up_failures after explore so contaminated agents
            # retry gear acquisition after discovering new area (may find gear station)
            contaminated = gear in ("scrambler", "scout")
            if contaminated and state.gear_up_failures >= 4:
                state.gear_up_failures = 0
                self._event(state, "contamination: reset gear_up_failures after explore")
            state.current_skill = None
        elif state.current_skill == "explore" and state.skill_steps >= self._stuck_threshold * 2:
            contaminated = gear in ("scrambler", "scout")
            if contaminated and state.gear_contamination_count >= 4:
                state.gear_contamination_count = 0
            self._event(state, f"explore capped after {state.skill_steps} steps without discovery")
            state.current_skill = None
        # Issue-36 v7: interrupt explore when get_heart cooldown expires.
        # Heartless aligners explore during cooldown. When cooldown expires, they should
        # immediately switch to get_heart instead of waiting for explore to find something.
        elif (
            state.current_skill == "explore"
            and gear == "aligner"
            and not has_heart
            and state.get_heart_cooldown_steps == 0
            and state.known_hubs
            and state.skill_steps > 0
        ):
            self._event(state, "explore interrupted: cooldown expired, switching to get_heart")
            state.current_skill = None
        # Issue-36 v9: interrupt explore when aligner has heart and alignable targets exist.
        # Aligner may discover enemy junctions during explore that aren't tracked by
        # explore_start_junctions (which only counts neutral). This ensures aligners
        # immediately switch to alignment when any target becomes available.
        elif (
            state.current_skill == "explore"
            and gear == "aligner"
            and has_heart
            and self._known_alignable_junctions(state)
            and state.skill_steps > 0
        ):
            self._event(state, f"explore interrupted: found {len(self._known_alignable_junctions(state))} alignable targets")
            state.current_skill = None
        elif state.current_skill == "defend" and has_heart and not state._prev_step_had_heart:
            self._event(state, "defend completed: acquired heart while defending, switching to align")
            state.get_heart_timeouts = 0
            state.consecutive_get_heart_failures = 0
            state.current_skill = None
        elif state.current_skill == "defend" and has_heart and gear == "aligner" and state.skill_steps > 0:
            _alignable_neutral = self._known_alignable_junctions(state)
            if _alignable_neutral:
                current_abs = self._current_abs(obs)
                nearest_alignable = self._aligner._nearest_known(current_abs, _alignable_neutral)
                alignable_dist = abs(nearest_alignable[0] - current_abs[0]) + abs(nearest_alignable[1] - current_abs[1]) if nearest_alignable else 9999
                if alignable_dist <= 25:
                    self._event(state, f"defend ended: alignable junction at dist={alignable_dist}")
                    state.get_heart_timeouts = 0
                    state.current_skill = None
        elif state.current_skill == "defend" and gear != "aligner" and state.skill_steps > 0:
            self._event(state, "defend ended: lost aligner gear")
            state.current_skill = None
        elif (
            state.current_skill == "defend"
            and not has_heart
            and gear == "aligner"
            and state.known_enemy_junctions
            and any(self._aligner._is_alignable(ej, state) for ej in state.known_enemy_junctions)
        ):
            self._event(state, "defend ended: reachable enemy junctions detected — rushing to get heart for recapture")
            state.get_heart_timeouts = 0
            state.current_skill = None
        elif (
            state.current_skill == "defend"
            and not has_heart
            and gear == "aligner"
            and self._shared_map is not None
            and self._shared_map.hearts_crafted_estimate > state.defend_start_hearts_estimate
        ):
            self._event(state, f"defend ended: new hearts available (crafted {self._shared_map.hearts_crafted_estimate} > {state.defend_start_hearts_estimate})")
            state.get_heart_timeouts = 0
            state.current_skill = None
        elif state.current_skill == "defend" and not has_heart and gear == "aligner" and state.skill_steps >= self._stuck_threshold * 4:
            self._event(state, f"defend ended: heartless for {state.skill_steps} steps, getting heart for recapture")
            state.get_heart_timeouts = 0
            state.current_skill = None
        elif state.current_skill == "defend" and state.skill_steps >= self._stuck_threshold * 20:
            self._event(state, f"defend recheck after {state.skill_steps} steps")
            state.get_heart_timeouts = 0
            state.current_skill = None
        elif state.current_skill == "unstuck" and state.skill_steps >= self._unstuck_horizon:
            self._event(state, "unstuck finished horizon")
            state.current_skill = None
        elif state.current_skill in {"gear_up_aligner", "gear_up_miner"} and state.skill_steps >= self._stuck_threshold * 10:
            state.gear_up_failures += 1
            state.gear_up_failures_total += 1
            self._event(state, f"{state.current_skill} timed out after {state.skill_steps} steps (failure #{state.gear_up_failures})")
            state.current_skill = None
        elif state.current_skill in {"mine_until_full", "deposit_to_hub"} and state.skill_steps >= self._stuck_threshold * 20:
            # Worker skills get a much longer timeout (400 steps with default threshold=20).
            # The baseline miner has NO timeout at all — skills run until completion.
            # Short timeouts waste 65% of step capacity in failed navigation to far hub/extractors.
            self._event(state, f"{state.current_skill} timed out after {state.skill_steps} steps (long-timeout)")
            state.current_skill = None
        elif state.current_skill in {"get_heart", "align_neutral"} and state.skill_steps >= self._stuck_threshold * 5:
            if state.current_skill == "align_neutral":
                state.align_neutral_timeouts += 1
                if state.align_neutral_timeouts >= 1:
                    current_abs = self._current_abs(obs)
                    non_bl_neutral = state.known_neutral_junctions - state.blacklisted_junctions
                    if non_bl_neutral:
                        stuck = self._aligner._nearest_known(current_abs, non_bl_neutral)
                        if stuck:
                            state.blacklisted_junctions.add(stuck)
                            state.align_neutral_timeouts = 0
            elif state.current_skill == "get_heart":
                state.get_heart_timeouts += 1
                state.consecutive_get_heart_failures += 1
                if self._shared_map is not None:
                    self._shared_map.agents_getting_hearts.discard(obs.agent_id)
            self._event(state, f"{state.current_skill} timed out after {state.skill_steps} steps")
            state.current_skill = None
        elif state.current_skill is not None and state.current_skill != "defend" and state.no_move_steps >= self._stuck_threshold:
            if state.current_skill == "deposit_to_hub":
                state.hub_approach_rotation = (state.hub_approach_rotation + 1) % 4
            if state.current_skill in {"gear_up_aligner", "gear_up_miner"}:
                state.gear_up_failures += 1
                state.gear_up_failures_total += 1
            if state.current_skill == "get_heart":
                state.consecutive_get_heart_failures += 1
                if self._shared_map is not None:
                    self._shared_map.agents_getting_hearts.discard(obs.agent_id)
            self._event(state, f"{state.current_skill} exited as stuck after {state.no_move_steps} blocked steps")
            state.current_skill = None
        elif state.current_skill == "get_heart" and state.no_progress_on_target_steps >= self._stuck_threshold // 2:
            # Issue-34 v12: Shorter stale threshold for get_heart (10 steps instead of 20).
            # Aligners waste less time camping at empty hub. Faster cycling means
            # more time spent exploring/aligning and more frequent heart pickup attempts.
            state.consecutive_get_heart_failures += 1
            if self._shared_map is not None:
                self._shared_map.agents_getting_hearts.discard(obs.agent_id)
            self._event(state, f"get_heart exited as stale after {state.no_progress_on_target_steps} steps (short threshold)")
            state.current_skill = None
        elif state.current_skill is not None and state.current_skill != "defend" and state.no_progress_on_target_steps >= self._stuck_threshold:
            # Issue-36 v12: remove depleted extractors — check adjacent cells too.
            # With V8 pre-blocking, miners are at approach cells (dist 1 from extractor),
            # not ON the extractor itself. Check current position AND adjacent cells.
            if state.current_skill == "mine_until_full":
                current_abs = self._current_abs(obs)
                nearby_extractors = {
                    e for e in state.known_extractors
                    if abs(current_abs[0] - e[0]) + abs(current_abs[1] - e[1]) <= 1
                }
                for e in nearby_extractors:
                    state.depleted_extractors.add(e)
                    state.known_extractors.discard(e)
                    for elem_set in state.extractors_by_element.values():
                        elem_set.discard(e)
                    state.verified_extractors.discard(e)
                    for elem_set in state.verified_extractors_by_element.values():
                        elem_set.discard(e)
                    self._event(state, f"removed depleted extractor at {e}")
            if state.current_skill == "deposit_to_hub":
                state.hub_approach_rotation = (state.hub_approach_rotation + 1) % 4
            if state.current_skill in {"gear_up_aligner", "gear_up_miner"}:
                state.gear_up_failures += 1
                state.gear_up_failures_total += 1
            if state.current_skill == "get_heart":
                state.consecutive_get_heart_failures += 1
                if self._shared_map is not None:
                    self._shared_map.agents_getting_hearts.discard(obs.agent_id)
            self._event(state, f"{state.current_skill} exited as stale after {state.no_progress_on_target_steps} steps")
            state.current_skill = None

    def _unstuck_move(self, state: CrossRoleState) -> tuple[Action, CrossRoleState]:
        """Escape pattern that avoids hard obstacles (walls), prefers non-move-blocked."""
        state.last_mode = "unstuck"
        current_abs = state.last_pos if state.last_pos else (0, 0)
        _DIR_DELTAS = {"north": (-1, 0), "east": (0, 1), "south": (1, 0), "west": (0, -1)}
        # First pass: avoid walls AND move-blocked
        for i in range(4):
            idx = (state.wander_direction_index + i) % len(self._UNSTUCK_DIRECTIONS)
            direction = self._UNSTUCK_DIRECTIONS[idx]
            dr, dc = _DIR_DELTAS[direction]
            neighbor = (current_abs[0] + dr, current_abs[1] + dc)
            if neighbor not in state.blocked_cells and neighbor not in state.move_blocked_cells:
                state.wander_direction_index = (idx + 1) % len(self._UNSTUCK_DIRECTIONS)
                return self._aligner._starter._action(f"move_{direction}"), state
        # Second pass: accept move-blocked (transient), avoid walls only
        for i in range(4):
            idx = (state.wander_direction_index + i) % len(self._UNSTUCK_DIRECTIONS)
            direction = self._UNSTUCK_DIRECTIONS[idx]
            dr, dc = _DIR_DELTAS[direction]
            neighbor = (current_abs[0] + dr, current_abs[1] + dc)
            if neighbor not in state.blocked_cells:
                state.wander_direction_index = (idx + 1) % len(self._UNSTUCK_DIRECTIONS)
                return self._aligner._starter._action(f"move_{direction}"), state
        # All blocked — cycle anyway
        direction = self._UNSTUCK_DIRECTIONS[state.wander_direction_index % len(self._UNSTUCK_DIRECTIONS)]
        state.wander_direction_index = (state.wander_direction_index + 1) % len(self._UNSTUCK_DIRECTIONS)
        return self._aligner._starter._action(f"move_{direction}"), state

    def _track_move_target(self, action: Action, current_abs: Coord, state: CrossRoleState) -> None:
        """Issue-36 v9: Set last_move_target for move failure tracking on early returns.

        Without this, retreat/tether moves that hit obstacles aren't tracked in
        move_blocked_cells, so BFS keeps routing through the same obstacles.
        """
        action_name = action.name if hasattr(action, "name") else ""
        if action_name.startswith("move_"):
            direction = action_name[len("move_"):]
            delta_map = {"north": (-1, 0), "east": (0, 1), "south": (1, 0), "west": (0, -1)}
            dr, dc = delta_map.get(direction, (0, 0))
            state.last_move_target = (current_abs[0] + dr, current_abs[1] + dc)

    def _navigate_to_station_safe(self, state: CrossRoleState, current_abs: Coord, target_abs: Coord) -> str | None:
        """Navigate to target station, returning None if next step would enter a hazard station.

        v10: delegates to _navigate_to_station (BFS → greedy fallback).
        v11 fix: _navigate_to_station's greedy fallback can step into hazard stations
        (e.g. when BFS fails and the greedy direction points toward scout/scrambler).
        After getting a direction, check if the immediate next cell is a known hazard station.
        If so, return None so the caller can explore safely instead of contaminating.
        """
        direction = self._aligner._navigate_to_station(state, current_abs, target_abs, avoid_hazards=True)
        if direction is None:
            return None
        # Verify the immediate next step doesn't land on a known hazard station
        _DIR_DELTA = {"north": (-1, 0), "south": (1, 0), "east": (0, 1), "west": (0, -1)}
        if direction in _DIR_DELTA:
            dr, dc = _DIR_DELTA[direction]
            next_cell = (current_abs[0] + dr, current_abs[1] + dc)
            if next_cell in state.known_hazard_stations:
                return None  # Would contaminate; caller should explore instead
        return direction

    def _gear_up_via_hub_step(self, obs: AgentObservation, state: CrossRoleState, current_abs: Coord) -> tuple[Action, CrossRoleState] | None:
        """v13: In phase 2, navigate to hub first before targeting gear station.

        Rationale: After phase switch, agents are near their phase-1 gear station. The
        phase-2 target station may be on the other side of the map, with hazards between them.
        The hub is central and well-connected; navigating via hub ensures agents are in a good
        position to find the new gear station without contamination.

        Returns None when hub has been reached (caller should proceed to gear station).
        """
        if state.phase != 2 or state.phase2_hub_cleared or not state.known_hubs:
            return None
        hub_abs = self._aligner._nearest_known(current_abs, state.known_hubs)
        if hub_abs is None:
            return None
        hub_dist = abs(current_abs[0] - hub_abs[0]) + abs(current_abs[1] - hub_abs[1])
        if hub_dist <= 3:
            state.phase2_hub_cleared = True
            self._event(state, "phase2 hub waypoint cleared; proceeding to gear station")
            return None
        direction = self._aligner._navigate_to_station(state, current_abs, hub_abs, avoid_hazards=True)
        if direction:
            return self._aligner._starter._action(f"move_{direction}"), state
        return None

    def _gear_up_aligner_safe(self, obs: AgentObservation, state: CrossRoleState, current_abs: Coord) -> tuple[Action, CrossRoleState]:
        """Gear up to aligner using hub-first waypoint (phase 2) then BFS-with-hazards → greedy.

        v6 fix: when BFS-with-hazards fails (path blocked by scout/scrambler), try
        BFS-without-hazards. Crossing other stations en route is acceptable since the
        aligner station will override any intermediate gear changes.
        v13 fix: in phase 2, navigate to hub first to reposition before targeting aligner station.
        Issue-36 v37: when hazard-safe nav fails, fall back to avoid_hazards=False.
        """
        hub_step = self._gear_up_via_hub_step(obs, state, current_abs)
        if hub_step is not None:
            return hub_step
        visible_target = self._aligner._starter._closest_tag_location(obs, self._aligner._aligner_station_tags)
        if visible_target is not None:
            target_abs = self._aligner._visible_abs_cell(current_abs, visible_target)
            direction = self._navigate_to_station_safe(state, current_abs, target_abs)
            if direction is None:
                direction = self._aligner._navigate_to_station(state, current_abs, target_abs, avoid_hazards=False)
            if direction is not None:
                return self._aligner._starter._action(f"move_{direction}"), state
            action, next_state = self._aligner._greedy_move_toward_abs(state, current_abs, target_abs)
            return action, state
        target_abs = self._aligner._nearest_known(current_abs, state.known_aligner_stations)
        if target_abs is None:
            if state.known_hubs:
                action, base_state = self._aligner._explore_near_hub(obs, state)
                return action, self._copy_with_shared(replace(state,
                    wander_direction_index=base_state.wander_direction_index,
                    wander_steps_remaining=base_state.wander_steps_remaining,
                    last_mode=base_state.last_mode,
                ))
            action, base_state = self._aligner._explore(obs, state)
            return action, self._copy_with_shared(replace(state,
                wander_direction_index=base_state.wander_direction_index,
                wander_steps_remaining=base_state.wander_steps_remaining,
                last_mode=base_state.last_mode,
            ))
        direction = self._navigate_to_station_safe(state, current_abs, target_abs)
        if direction is None:
            direction = self._aligner._navigate_to_station(state, current_abs, target_abs, avoid_hazards=False)
        if direction is not None:
            return self._aligner._starter._action(f"move_{direction}"), state
        action, next_state = self._aligner._greedy_move_toward_abs(state, current_abs, target_abs)
        return action, state

    def _gear_up_miner_safe(self, obs: AgentObservation, state: CrossRoleState, current_abs: Coord) -> tuple[Action, CrossRoleState]:
        """Gear up to miner using hub-first waypoint (phase 2) then BFS-with-hazards → greedy.

        Issue-12 fix: the original miner._gear_up uses _move_toward_target which falls back
        to optimistic BFS without hazard avoidance when the primary BFS fails. This causes
        agents to route through scout/scrambler/aligner stations, accidentally equipping
        wrong gear. This version uses the aligner's _navigate_to_station with avoid_hazards=True
        and an expanded 1-cell buffer zone around hazard stations.
        v6 fix: adds BFS-without-hazards as fallback before greedy navigation.
        v13 fix: in phase 2, navigate to hub first to reposition before targeting miner station.
        Issue-36 v37: when hazard-safe nav fails, fall back to avoid_hazards=False. Walking
        through a wrong station is better than being permanently stuck without gear.
        """
        hub_step = self._gear_up_via_hub_step(obs, state, current_abs)
        if hub_step is not None:
            return hub_step
        visible_target = self._miner._closest_visible_location(obs, self._miner._miner_station_tags)
        if visible_target is not None:
            target_abs = self._miner._visible_abs_cell(current_abs, visible_target)
            direction = self._navigate_to_station_safe(state, current_abs, target_abs)
            if direction is None:
                direction = self._aligner._navigate_to_station(state, current_abs, target_abs, avoid_hazards=False)
            if direction is not None:
                return self._aligner._starter._action(f"move_{direction}"), state
            action, next_state = self._aligner._greedy_move_toward_abs(state, current_abs, target_abs)
            return action, state
        target_abs = self._aligner._nearest_known(current_abs, state.known_miner_stations)
        if target_abs is None:
            if state.known_hubs:
                action, base_state = self._aligner._explore_near_hub(obs, state)
                return action, self._copy_with_shared(replace(state,
                    wander_direction_index=base_state.wander_direction_index,
                    wander_steps_remaining=base_state.wander_steps_remaining,
                    last_mode=base_state.last_mode,
                ))
            action, base_state = self._aligner._explore(obs, state)
            return action, self._copy_with_shared(replace(state,
                wander_direction_index=base_state.wander_direction_index,
                wander_steps_remaining=base_state.wander_steps_remaining,
                last_mode=base_state.last_mode,
            ))
        direction = self._navigate_to_station_safe(state, current_abs, target_abs)
        if direction is None:
            direction = self._aligner._navigate_to_station(state, current_abs, target_abs, avoid_hazards=False)
        if direction is not None:
            return self._aligner._starter._action(f"move_{direction}"), state
        action, next_state = self._aligner._greedy_move_toward_abs(state, current_abs, target_abs)
        return action, state

    def _handle_phase_switch(self, obs: AgentObservation, state: CrossRoleState) -> None:
        """At phase switch step, flip preferred gear and reset gear acquisition state."""
        gear = self._current_gear(obs)
        effective_preferred = state.phase_preferred_gear or self._preferred_initial_gear
        new_preferred = "miner" if effective_preferred == "aligner" else "aligner"
        logger.info(
            "PHASE_SWITCH agent=%d step=%d current_gear=%s old_preferred=%s new_preferred=%s",
            obs.agent_id, state.episode_step, gear, effective_preferred, new_preferred,
        )
        state.phase = 2
        state.phase_preferred_gear = new_preferred
        state.gear_up_completed = False
        state.gear_up_failures = 0
        state.current_skill = None
        self._clear_shared_map_tracking(obs.agent_id)  # Issue-36 v19
        state.phase2_hub_cleared = False  # v13: reset hub waypoint for hub-first navigation

    def step_with_state(self, obs: AgentObservation, state: CrossRoleState) -> tuple[Action, CrossRoleState]:
        try:
            return self._step_impl(obs, state)
        except Exception as e:
            logger.warning("agent=%s role=cross_role step_error=%s — returning noop", obs.agent_id, e)
            return self._aligner._starter._action("noop"), state

    def _step_impl(self, obs: AgentObservation, state: CrossRoleState) -> tuple[Action, CrossRoleState]:
        state.episode_step += 1

        # Issue-36 v9: periodic blacklist expiry (every 500 steps).
        # Blacklisted junctions were marked unreachable due to align_neutral timeouts.
        # Navigation improvements (V8) may have made them reachable. Allow periodic retry.
        _BLACKLIST_EXPIRY_INTERVAL = 500
        if state.episode_step % _BLACKLIST_EXPIRY_INTERVAL == 0 and state.blacklisted_junctions:
            count = len(state.blacklisted_junctions)
            state.blacklisted_junctions.clear()
            self._event(state, f"blacklist expired: cleared {count} junctions for retry")

        # Phase switch: flip preferred gear at phase_switch_step
        if self._phase_switch_step > 0 and state.episode_step == self._phase_switch_step and state.phase == 1:
            self._handle_phase_switch(obs, state)

        # Log gear state at key steps for metric computation
        if self._phase_switch_step > 0 and state.episode_step in (self._phase_switch_step, self._phase_switch_step * 2):
            gear = self._current_gear(obs)
            effective_preferred = state.phase_preferred_gear or self._preferred_initial_gear
            logger.info(
                "GEAR_STATE agent=%d step=%d gear=%s phase=%d intended=%s",
                obs.agent_id, state.episode_step, gear, state.phase, effective_preferred,
            )

        current_abs = self._update_map_memory(obs, state)
        self._update_progress(obs, state)

        gear = self._current_gear(obs)
        _CONTAMINATION_GEARS = {"scrambler", "scout"}
        if state._prev_gear in ("aligner", "miner") and gear in _CONTAMINATION_GEARS:
            state.contamination_avoid_cells.add(current_abs)
            state.gear_contamination_count += 1
            logger.info("agent=%s GEAR_CONTAMINATED at %s (now %s, count=%d)",
                        obs.agent_id, current_abs, gear, state.gear_contamination_count)
        state._prev_gear = gear

        _CONTAMINATION_EXPIRY_INTERVAL = 500
        if state.episode_step % _CONTAMINATION_EXPIRY_INTERVAL == 0 and state.contamination_avoid_cells:
            count = len(state.contamination_avoid_cells)
            state.contamination_avoid_cells.clear()
            self._event(state, f"contamination cells expired: cleared {count} cells")

        self._maybe_finish_skill(obs, state)

        _BASE_HP = 100
        current_hp = self._inventory_count(obs, "hp")
        if current_hp > state.max_hp_seen:
            state.max_hp_seen = min(current_hp, _BASE_HP)
        if state.max_hp_seen > 0:
            hp_fraction = current_hp / state.max_hp_seen
            in_friendly = self._aligner._in_friendly_territory(current_abs, state)
            dist_to_safe = self._dist_to_nearest_safe(current_abs, state)
            effective_threshold = _HP_RETREAT_THRESHOLD
            if dist_to_safe > 40:
                effective_threshold = min(0.85, _HP_RETREAT_THRESHOLD + 0.15)
            elif dist_to_safe > 25:
                effective_threshold = _HP_RETREAT_THRESHOLD + 0.05
            if hp_fraction < effective_threshold and not in_friendly and not state.retreating:
                state.retreating = True
                state.retreat_stuck_steps = 0
                state.current_skill = None
                self._clear_shared_map_tracking(obs.agent_id)
                self._event(state, f"HP retreat: hp={current_hp}/{state.max_hp_seen} ({hp_fraction:.0%}) dist_safe={dist_to_safe}")
                logger.info("agent=%s HP_RETREAT hp=%d/%d frac=%.2f dist_safe=%d", obs.agent_id, current_hp, state.max_hp_seen, hp_fraction, dist_to_safe)
            elif state.retreating and (in_friendly or hp_fraction >= 0.85):
                state.retreating = False
                state.retreat_stuck_steps = 0
                state.current_skill = None
                self._clear_shared_map_tracking(obs.agent_id)
                self._event(state, f"HP recovered: hp={current_hp}/{state.max_hp_seen} ({hp_fraction:.0%}) in_friendly={in_friendly}")
                logger.info("agent=%s HP_RECOVERED hp=%d/%d in_friendly=%s", obs.agent_id, current_hp, state.max_hp_seen, in_friendly)

        # Issue-36 v6: miner hub tethering — prevent miners from wandering too far from hub.
        # Miners that explore beyond MAX_HUB_DISTANCE can't retreat in time when HP drops.
        # At 70% HP threshold, agents have ~30 steps to reach hub. Keep miners within range.
        _MAX_HUB_DISTANCE = 40
        gear = self._current_gear(obs)
        if (
            not state.retreating
            and gear == "miner"
            and state.known_hubs
            and state.current_skill in {"explore", "mine_until_full"}
        ):
            hub_abs = self._aligner._nearest_known(current_abs, state.known_hubs)
            if hub_abs is not None:
                hub_dist = abs(current_abs[0] - hub_abs[0]) + abs(current_abs[1] - hub_abs[1])
                if hub_dist > _MAX_HUB_DISTANCE:
                    # Too far from hub — set skill to deposit (if carrying) or explore near hub.
                    # Issue-36 v7: previously set current_skill=None, causing oscillation:
                    # tether→navigate back→replan→mine_until_full→tether again. Now we set
                    # a concrete skill so the miner does something useful near hub.
                    carried = self._carried_total(obs)
                    if carried > 0:
                        state.current_skill = "deposit_to_hub"
                        state.current_reason = f"miner tether: deposit {carried} cargo (dist {hub_dist} > {_MAX_HUB_DISTANCE})"
                    else:
                        state.current_skill = "explore"
                        state.current_reason = f"miner tether: explore near hub (dist {hub_dist} > {_MAX_HUB_DISTANCE})"
                        state.explore_start_junctions = len(state.known_neutral_junctions) + len(state.known_enemy_junctions) + len(state.known_friendly_junctions)
                        state.explore_start_extractors = len(state.known_extractors) + len(state.depleted_extractors)
                    state.skill_steps = 0
                    state.no_move_steps = 0
                    state.no_progress_on_target_steps = 0
                    self._event(state, f"miner hub tether: distance {hub_dist} > {_MAX_HUB_DISTANCE}, {state.current_skill}")
                    logger.info("agent=%s MINER_TETHER dist=%d skill=%s carried=%d", obs.agent_id, hub_dist, state.current_skill, carried)
                    direction = self._aligner._navigate_to_station(state, current_abs, hub_abs, avoid_hazards=True)
                    if direction:
                        action = self._aligner._starter._action(f"move_{direction}")
                        self._track_move_target(action, current_abs, state)
                        return action, state
                    action, base_state = self._aligner._greedy_move_toward_abs(state, current_abs, hub_abs, avoid_hazards=True)
                    state = self._copy_with_shared(replace(state,
                        wander_direction_index=base_state.wander_direction_index,
                        wander_steps_remaining=base_state.wander_steps_remaining,
                        last_mode=base_state.last_mode,
                    ))
                    self._track_move_target(action, current_abs, state)
                    return action, state

        # Issue-36 v11: aligner hub tethering — prevent aligners from wandering too far
        # from hub during explore. _is_alignable limits junction targets to 25 cells from
        # hub, so aligners should stay within ~35 cells. Beyond that, retreat at 70% HP
        # may not reach hub in time (~30 steps to navigate back).
        _MAX_ALIGNER_TERRITORY_DISTANCE = 35
        if (
            not state.retreating
            and gear == "aligner"
            and state.known_hubs
            and state.current_skill == "explore"
        ):
            hub_abs = self._aligner._nearest_known(current_abs, state.known_hubs)
            friendly_anchors = set(state.known_hubs) | state.known_friendly_junctions
            nearest_anchor = self._aligner._nearest_known(current_abs, friendly_anchors)
            territory_dist = abs(current_abs[0] - nearest_anchor[0]) + abs(current_abs[1] - nearest_anchor[1]) if nearest_anchor else 9999
            if hub_abs is not None and territory_dist > _MAX_ALIGNER_TERRITORY_DISTANCE:
                    has_heart = self._inventory_count(obs, "heart") > 0
                    if has_heart and self._known_alignable_junctions(state):
                        state.current_skill = "align_neutral"
                        state.current_reason = f"aligner tether: align nearest target (territory_dist {territory_dist} > {_MAX_ALIGNER_TERRITORY_DISTANCE})"
                    else:
                        state.current_skill = "get_heart" if not has_heart and state.known_hubs else "explore"
                        state.current_reason = f"aligner tether: return toward hub (territory_dist {territory_dist} > {_MAX_ALIGNER_TERRITORY_DISTANCE})"
                    self._clear_shared_map_tracking(obs.agent_id)
                    if self._shared_map is not None and state.current_skill == "get_heart":
                        self._shared_map.agents_getting_hearts.add(obs.agent_id)
                        state.get_heart_start_count = self._inventory_count(obs, "heart")
                    state.skill_steps = 0
                    state.no_move_steps = 0
                    state.no_progress_on_target_steps = 0
                    if state.current_skill == "explore":
                        state.explore_start_junctions = len(state.known_neutral_junctions) + len(state.known_enemy_junctions) + len(state.known_friendly_junctions)
                        state.explore_start_extractors = len(state.known_extractors) + len(state.depleted_extractors)
                    self._event(state, f"aligner tether: territory_dist {territory_dist} > {_MAX_ALIGNER_TERRITORY_DISTANCE}, {state.current_skill}")
                    logger.info("agent=%s ALIGNER_TETHER territory_dist=%d skill=%s", obs.agent_id, territory_dist, state.current_skill)
                    direction = self._aligner._navigate_to_station(state, current_abs, hub_abs, avoid_hazards=True)
                    if direction:
                        action = self._aligner._starter._action(f"move_{direction}")
                        self._track_move_target(action, current_abs, state)
                        return action, state
                    action, base_state = self._aligner._greedy_move_toward_abs(state, current_abs, hub_abs, avoid_hazards=True)
                    state = self._copy_with_shared(replace(state,
                        wander_direction_index=base_state.wander_direction_index,
                        wander_steps_remaining=base_state.wander_steps_remaining,
                        last_mode=base_state.last_mode,
                    ))
                    self._track_move_target(action, current_abs, state)
                    return action, state

        if state.retreating and state.known_hubs:
            last_action_move = self._feature_value(obs, "last_action_move")
            if last_action_move == 0:
                state.retreat_stuck_steps += 1
            else:
                state.retreat_stuck_steps = 0

            _RETREAT_STUCK_LIMIT = 50
            _RETREAT_GIVE_UP_LIMIT = 100
            if state.retreat_stuck_steps >= _RETREAT_GIVE_UP_LIMIT:
                state.retreating = False
                state.retreat_stuck_steps = 0
                state.current_skill = None
                self._clear_shared_map_tracking(obs.agent_id)
                self._event(state, f"retreat cancelled: stuck for {_RETREAT_GIVE_UP_LIMIT} steps, replanning")
                logger.info("agent=%s RETREAT_CANCELLED stuck=%d, giving up retreat", obs.agent_id, _RETREAT_GIVE_UP_LIMIT)
            elif state.retreat_stuck_steps == _RETREAT_STUCK_LIMIT:
                state.move_cooldowns.clear()
                if hasattr(state, 'move_blocked_cells'):
                    state.move_blocked_cells.clear()
                self._event(state, f"retreat stuck: cleared cooldowns after {_RETREAT_STUCK_LIMIT} steps")

            elif state.retreat_stuck_steps >= 5 and state.retreat_stuck_steps % 3 == 0:
                action, state = self._unstuck_move(state)
                self._track_move_target(action, current_abs, state)
                return action, state

            else:
                _retreat_hubs = state.verified_hubs if state.verified_hubs else state.known_hubs
                retreat_targets = _retreat_hubs | state.known_friendly_junctions
                retreat_gear = self._current_gear(obs)
                retreat_heart = self._inventory_count(obs, "heart") > 0
                if retreat_gear == "aligner" and retreat_heart:
                    alignable = self._known_alignable_junctions(state)
                    if alignable:
                        nearest_alignable = self._aligner._nearest_known(current_abs, alignable)
                        if nearest_alignable is not None:
                            al_dist = abs(nearest_alignable[0] - current_abs[0]) + abs(nearest_alignable[1] - current_abs[1])
                            safe_dist = min(
                                (abs(t[0] - current_abs[0]) + abs(t[1] - current_abs[1]) for t in retreat_targets),
                                default=9999,
                            ) if retreat_targets else 9999
                            if al_dist < safe_dist and al_dist <= 10:
                                action, base_state = self._aligner._move_to(state, current_abs, nearest_alignable)
                                state = self._copy_with_shared(replace(state,
                                    wander_direction_index=base_state.wander_direction_index,
                                    wander_steps_remaining=base_state.wander_steps_remaining,
                                    last_mode=base_state.last_mode,
                                ))
                                self._track_move_target(action, current_abs, state)
                                return action, state
                target = self._aligner._nearest_known(current_abs, retreat_targets) if retreat_targets else None
                if target is not None:
                    is_hub = target in _retreat_hubs
                    dist = abs(current_abs[0] - target[0]) + abs(current_abs[1] - target[1])
                    if dist <= 2:
                        state.retreat_stuck_steps = 0
                        if is_hub:
                            carried = self._carried_total(obs)
                            gear = self._current_gear(obs)
                            has_heart = self._inventory_count(obs, "heart") > 0
                            wants_hub_interaction = (
                                (gear == "miner" and carried > 0)
                                or (gear != "miner" and not has_heart)
                            )
                            if dist == 1 and wants_hub_interaction:
                                dr = target[0] - current_abs[0]
                                dc = target[1] - current_abs[1]
                                if abs(dr) >= abs(dc):
                                    direction = "south" if dr > 0 else "north"
                                else:
                                    direction = "east" if dc > 0 else "west"
                                if gear == "miner":
                                    self._event(state, f"emergency deposit: miner stepping into hub with {carried} cargo")
                                else:
                                    self._event(state, "retreat hub interaction: stepping into hub to collect heart")
                                action = self._aligner._starter._action(f"move_{direction}")
                                self._track_move_target(action, current_abs, state)
                                return action, state
                            if dist == 2 and wants_hub_interaction:
                                direction = self._aligner._navigate_to_station(state, current_abs, target, avoid_hazards=True)
                                if direction:
                                    action = self._aligner._starter._action(f"move_{direction}")
                                    self._track_move_target(action, current_abs, state)
                                    return action, state
                        return self._aligner._starter._action("noop"), state
                    if target in state.known_free_cells:
                        action, base_state = self._aligner._move_to(state, current_abs, target)
                        state = self._copy_with_shared(replace(state,
                            wander_direction_index=base_state.wander_direction_index,
                            wander_steps_remaining=base_state.wander_steps_remaining,
                            last_mode=base_state.last_mode,
                        ))
                        self._track_move_target(action, current_abs, state)
                        return action, state
                    direction = self._aligner._navigate_to_station(state, current_abs, target, avoid_hazards=True)
                    if direction is None:
                        direction = self._aligner._navigate_to_station(state, current_abs, target, avoid_hazards=False)
                    if direction:
                        action = self._aligner._starter._action(f"move_{direction}")
                        self._track_move_target(action, current_abs, state)
                        return action, state
                    action, base_state = self._aligner._greedy_move_toward_abs(state, current_abs, target, avoid_hazards=True)
                    state = self._copy_with_shared(replace(state,
                        wander_direction_index=base_state.wander_direction_index,
                        wander_steps_remaining=base_state.wander_steps_remaining,
                        last_mode=base_state.last_mode,
                    ))
                    self._track_move_target(action, current_abs, state)
                    return action, state

        if state.current_skill is None:
            self._plan_skill(obs, state)

        # Issue-35: Progressive evasion on consecutive move failures.
        # Step 1: perpendicular dodge (clockwise rotation)
        # Step 2: other perpendicular (counter-clockwise rotation)
        # Step 3: reverse direction
        # Step 5+: navigation shake (existing unstuck mechanism)
        _DIR_LOOKUP = (("north", (-1, 0)), ("east", (0, 1)), ("south", (1, 0)), ("west", (0, -1)))
        if (state.current_skill not in {None, "unstuck", "defend"}
                and 1 <= state.no_move_steps <= 3
                and state.last_pos is not None
                and state.last_move_target is not None
                and current_abs == state.last_pos):
            failed_dr = state.last_move_target[0] - current_abs[0]
            failed_dc = state.last_move_target[1] - current_abs[1]
            if state.no_move_steps == 1:
                # Perpendicular (clockwise rotation)
                evasion_options = [(-failed_dc, failed_dr), (failed_dc, -failed_dr)]
            elif state.no_move_steps == 2:
                # Other perpendicular (counter-clockwise first)
                evasion_options = [(failed_dc, -failed_dr), (-failed_dc, failed_dr)]
            else:  # no_move_steps == 3
                # Reverse direction
                evasion_options = [(-failed_dr, -failed_dc)]
            blocked = state.blocked_cells
            for pdr, pdc in evasion_options:
                if pdr == 0 and pdc == 0:
                    continue
                neighbor = (current_abs[0] + pdr, current_abs[1] + pdc)
                if neighbor not in blocked:
                    for dir_name, (ddr, ddc) in _DIR_LOOKUP:
                        if (ddr, ddc) == (pdr, pdc):
                            state.skill_steps += 1
                            state.last_move_target = neighbor
                            return self._aligner._starter._action(f"move_{dir_name}"), state
        # Navigation shake to break stuck loops (fires after 5+ consecutive failures)
        if state.current_skill not in {None, "unstuck", "defend"} and state.no_move_steps >= 5 and state.no_move_steps % 3 == 0:
            action, state = self._unstuck_move(state)
            state.skill_steps += 1
            self._track_move_target(action, current_abs, state)
            return action, state

        skill = state.current_skill

        if skill == "gear_up_aligner":
            # v5: when agent has miner gear, miner station is safe to pass through
            # (re-equips same gear → no net change; removes it as a navigation blocker)
            gear = self._current_gear(obs)
            if state.gear_up_failures >= 5:
                # Issue-34 v11: After 5+ gear_up failures, disable hazard avoidance entirely.
                # The agent can't find a safe path to the aligner station (likely blocked by
                # hazard stations). Allow routing through scout/scrambler stations — the
                # intermediate contamination is transient since the aligner station will
                # override any gear change upon arrival.
                nav_state = replace(state, known_hazard_stations=set())
                logger.info("agent=%s gear_up_aligner hazard_bypass: failures=%d, clearing hazard avoidance",
                            obs.agent_id, state.gear_up_failures)
            elif gear == "miner" and state.known_miner_stations:
                nav_state = replace(state, known_hazard_stations=state.known_hazard_stations - state.known_miner_stations)
            else:
                nav_state = state
            action, base_state = self._gear_up_aligner_safe(obs, nav_state, current_abs)
            state = self._copy_with_shared(replace(state,
                wander_direction_index=base_state.wander_direction_index,
                wander_steps_remaining=base_state.wander_steps_remaining,
                last_mode=base_state.last_mode,
                last_pos=getattr(base_state, 'last_pos', state.last_pos),
                last_move_target=getattr(base_state, 'last_move_target', state.last_move_target),
                phase2_hub_cleared=base_state.phase2_hub_cleared,  # v13: persist hub waypoint state
            ))

        elif skill == "gear_up_miner":
            # Use safe version: hazard-aware navigation (avoids other gear stations)
            # v5: when agent has aligner gear, aligner station is safe to pass through
            gear = self._current_gear(obs)
            if state.gear_up_failures >= 5:
                # Issue-34 v11: same hazard bypass as gear_up_aligner
                aligner_nav_state = replace(state, known_hazard_stations=set())
            elif gear == "aligner" and state.known_aligner_stations:
                aligner_nav_state = replace(state, known_hazard_stations=state.known_hazard_stations - state.known_aligner_stations)
            else:
                aligner_nav_state = state
            action, base_state = self._gear_up_miner_safe(obs, aligner_nav_state, current_abs)
            state = self._copy_with_shared(replace(state,
                wander_direction_index=base_state.wander_direction_index,
                wander_steps_remaining=base_state.wander_steps_remaining,
                last_mode=base_state.last_mode,
                last_pos=base_state.last_pos,
                last_move_target=getattr(base_state, 'last_move_target', state.last_move_target),
                phase2_hub_cleared=base_state.phase2_hub_cleared,  # v13: persist hub waypoint state
            ))

        elif skill == "get_heart":
            action, base_state = self._aligner._get_heart(obs, state, current_abs)
            state = self._copy_with_shared(replace(state,
                wander_direction_index=base_state.wander_direction_index,
                wander_steps_remaining=base_state.wander_steps_remaining,
                last_mode=base_state.last_mode,
                last_pos=base_state.last_pos,
                last_move_target=base_state.last_move_target,
            ))

        elif skill == "align_neutral":
            # Only navigate to neutral junctions — enemy junctions have a team tag and
            # can't be aligned directly (isNot(hasTagPrefix("team:")) filter).
            sm = self._shared_map
            if sm is not None:
                yield_targets = set()
                for aid, t in sm.aligner_targets.items():
                    if aid == obs.agent_id or t is None:
                        continue
                    other_pos = sm.agent_positions.get(aid)
                    if other_pos is None:
                        yield_targets.add(t)
                        continue
                    their_dist = abs(t[0] - other_pos[0]) + abs(t[1] - other_pos[1])
                    my_dist = abs(t[0] - current_abs[0]) + abs(t[1] - current_abs[1])
                    if their_dist <= my_dist:
                        yield_targets.add(t)
                if yield_targets:
                    saved_bl = set(state.blacklisted_junctions)
                    state.blacklisted_junctions |= yield_targets
                    action, base_state = self._aligner._align_neutral(obs, state, current_abs)
                    state.blacklisted_junctions = saved_bl
                else:
                    action, base_state = self._aligner._align_neutral(obs, state, current_abs)
                bl = state.blacklisted_junctions
                predict_alignable = {j for j in state.known_neutral_junctions
                                     if self._aligner._is_alignable(j, state) and j not in bl and j not in yield_targets}
                sm.aligner_targets[obs.agent_id] = self._aligner._cascade_priority_target(current_abs, predict_alignable, state)
            else:
                action, base_state = self._aligner._align_neutral(obs, state, current_abs)
            state = self._copy_with_shared(replace(state,
                wander_direction_index=base_state.wander_direction_index,
                wander_steps_remaining=base_state.wander_steps_remaining,
                last_mode=base_state.last_mode,
                last_pos=base_state.last_pos,
                last_move_target=base_state.last_move_target,
            ))

        elif skill == "mine_until_full":
            action, base_state = self._miner._mine_until_full(obs, state)
            state = self._copy_with_shared(replace(state,
                wander_direction_index=base_state.wander_direction_index,
                wander_steps_remaining=base_state.wander_steps_remaining,
                last_mode=base_state.last_mode,
                remembered_hub_row_from_spawn=base_state.remembered_hub_row_from_spawn,
                remembered_hub_col_from_spawn=base_state.remembered_hub_col_from_spawn,
                last_pos=base_state.last_pos,
                last_move_target=base_state.last_move_target,
            ))

        elif skill == "deposit_to_hub":
            # Issue-36 v14: friendly junctions have deposit handlers that send resources
            # directly to hub. If a friendly junction is closer than hub, navigate there
            # instead. Junctions are walkable — miner walks onto junction, deposit handler
            # fires (FirstMatch: deposit before scramble/align), cargo goes to hub.
            junction_target = self._aligner._nearest_known(current_abs, state.known_friendly_junctions)
            hub_target = self._aligner._nearest_known(current_abs, state.known_hubs)
            use_junction = False
            if junction_target is not None and hub_target is not None:
                jdist = abs(junction_target[0] - current_abs[0]) + abs(junction_target[1] - current_abs[1])
                hdist = abs(hub_target[0] - current_abs[0]) + abs(hub_target[1] - current_abs[1])
                use_junction = jdist < hdist  # strict less-than: prefer hub on tie
            if use_junction:
                # Navigate to friendly junction (walkable — direct BFS, no approach cell needed)
                direction = self._aligner._bfs_first_direction(state, current_abs, junction_target, avoid_hazards=True)
                if direction is None:
                    direction = self._aligner._bfs_without_cooldowns(state, current_abs, junction_target, avoid_hazards=True)
                if direction is None:
                    direction = self._aligner._bfs_optimistic_direction(state, current_abs, junction_target, avoid_hazards=True)
                if direction is None:
                    direction = self._aligner._bfs_first_direction(state, current_abs, junction_target, avoid_hazards=False)
                if direction is None:
                    direction = self._aligner._bfs_optimistic_direction(state, current_abs, junction_target, avoid_hazards=False)
                if direction is not None:
                    action = self._aligner._starter._action(f"move_{direction}")
                    state.last_move_target = self._aligner._move_target(current_abs, direction)
                else:
                    # Fallback to normal hub deposit
                    action, base_state = self._miner._deposit_to_hub(obs, state)
                    state = self._copy_with_shared(replace(state,
                        wander_direction_index=base_state.wander_direction_index,
                        wander_steps_remaining=base_state.wander_steps_remaining,
                        last_mode=base_state.last_mode,
                        remembered_hub_row_from_spawn=base_state.remembered_hub_row_from_spawn,
                        remembered_hub_col_from_spawn=base_state.remembered_hub_col_from_spawn,
                        last_pos=base_state.last_pos,
                        last_move_target=base_state.last_move_target,
                    ))
            else:
                action, base_state = self._miner._deposit_to_hub(obs, state)
                state = self._copy_with_shared(replace(state,
                    wander_direction_index=base_state.wander_direction_index,
                    wander_steps_remaining=base_state.wander_steps_remaining,
                    last_mode=base_state.last_mode,
                    remembered_hub_row_from_spawn=base_state.remembered_hub_row_from_spawn,
                    remembered_hub_col_from_spawn=base_state.remembered_hub_col_from_spawn,
                    last_pos=base_state.last_pos,
                    last_move_target=base_state.last_move_target,
                ))

        elif skill == "defend":
            # Issue-16: navigate toward friendly junction with highest defend value.
            # Prefer bridge junctions (cascade risk) near enemy territory.
            fj = state.known_friendly_junctions
            ej = state.known_enemy_junctions
            kh = state.known_hubs
            sm = self._shared_map
            other_positions = set()
            if sm is not None:
                for aid, pos in sm.agent_positions.items():
                    if aid != obs.agent_id:
                        other_positions.add(pos)
            def _cr_defend_score(j):
                travel = abs(j[0] - current_abs[0]) + abs(j[1] - current_abs[1])
                threat = 0.0
                if ej:
                    nearest_enemy = min(abs(j[0] - e[0]) + abs(j[1] - e[1]) for e in ej)
                    threat = max(0, 30 - nearest_enemy) * 0.5
                cascade = 0
                for f in fj:
                    if f == j or abs(f[0] - j[0]) + abs(f[1] - j[1]) > _JUNCTION_ALIGN_DISTANCE:
                        continue
                    has_other = any(abs(f[0] - h[0]) + abs(f[1] - h[1]) <= _HUB_ALIGN_DISTANCE for h in kh)
                    if not has_other:
                        has_other = any(
                            abs(f[0] - o[0]) + abs(f[1] - o[1]) <= _JUNCTION_ALIGN_DISTANCE
                            for o in fj if o != j and o != f
                        )
                    if not has_other:
                        cascade += 1
                spread = min((abs(j[0] - p[0]) + abs(j[1] - p[1]) for p in other_positions), default=0)
                return spread * 0.5 - travel * 0.3 + threat + cascade * 3.0
            if len(fj) > 1 and other_positions:
                target = max(fj, key=_cr_defend_score)
            else:
                target = self._aligner._nearest_known(current_abs, fj)
            if target is not None:
                action = None
                dist = abs(current_abs[0] - target[0]) + abs(current_abs[1] - target[1])
                if current_abs in fj:
                    state.defend_station_steps += 1
                    patrol_interval = 10 if ej else 40
                    if state.defend_station_steps >= patrol_interval and len(fj) > 1:
                        other_junctions = fj - {current_abs}
                        if len(other_junctions) > 1 and other_positions:
                            target = max(other_junctions, key=_cr_defend_score)
                        else:
                            target = self._aligner._nearest_known(current_abs, other_junctions)
                        state.defend_last_junction = current_abs
                        state.defend_station_steps = 0
                    elif len(fj) <= 1 and state.defend_station_steps >= 10:
                        action, base_state = self._aligner._explore_for_alignment(obs, state)
                        state = self._copy_with_shared(replace(state,
                            wander_direction_index=base_state.wander_direction_index,
                            wander_steps_remaining=base_state.wander_steps_remaining,
                            last_mode=base_state.last_mode,
                            last_pos=getattr(base_state, 'last_pos', state.last_pos),
                            last_move_target=getattr(base_state, 'last_move_target', state.last_move_target),
                        ))
                        target = None
                    else:
                        action = self._aligner._starter._action("noop")
                        target = None
                    if target is not None:
                        dist = abs(current_abs[0] - target[0]) + abs(current_abs[1] - target[1])
                if target is not None and dist > 0 and action is None:
                    if target in state.known_free_cells:
                        action, base_state = self._aligner._move_to(state, current_abs, target)
                        state = self._copy_with_shared(replace(state,
                            wander_direction_index=base_state.wander_direction_index,
                            wander_steps_remaining=base_state.wander_steps_remaining,
                            last_mode=base_state.last_mode,
                            last_pos=getattr(base_state, 'last_pos', state.last_pos),
                            last_move_target=getattr(base_state, 'last_move_target', state.last_move_target),
                        ))
                    else:
                        direction = self._aligner._navigate_to_station(state, current_abs, target, avoid_hazards=True)
                        if direction:
                            action = self._aligner._starter._action(f"move_{direction}")
                        else:
                            action, base_state = self._aligner._greedy_move_toward_abs(state, current_abs, target, avoid_hazards=True)
                            state = self._copy_with_shared(replace(state,
                                wander_direction_index=base_state.wander_direction_index,
                                wander_steps_remaining=base_state.wander_steps_remaining,
                                last_mode=base_state.last_mode,
                                last_pos=getattr(base_state, 'last_pos', state.last_pos),
                                last_move_target=getattr(base_state, 'last_move_target', state.last_move_target),
                            ))
            else:
                # No friendly junctions known — explore near hub to stay safe
                if state.known_hubs:
                    action, base_state = self._aligner._explore_near_hub(obs, state)
                else:
                    action, base_state = self._aligner._explore(obs, state)
                state = self._copy_with_shared(replace(state,
                    wander_direction_index=base_state.wander_direction_index,
                    wander_steps_remaining=base_state.wander_steps_remaining,
                    last_mode=base_state.last_mode,
                    last_pos=getattr(base_state, 'last_pos', state.last_pos),
                    last_move_target=getattr(base_state, 'last_move_target', state.last_move_target),
                ))

        elif skill == "explore":
            gear = self._current_gear(obs)
            has_heart = self._inventory_count(obs, "heart") > 0
            if gear == "aligner" and has_heart:
                action, base_state = self._aligner._explore_for_alignment(obs, state)
                state = self._copy_with_shared(replace(state,
                    wander_direction_index=base_state.wander_direction_index,
                    wander_steps_remaining=base_state.wander_steps_remaining,
                    last_mode=base_state.last_mode,
                    last_pos=getattr(base_state, 'last_pos', state.last_pos),
                    last_move_target=getattr(base_state, 'last_move_target', state.last_move_target),
                ))
            elif gear == "miner":
                # Use miner-specific explore to stay near hub/extractor areas (avoids junction/scout areas)
                if state.known_hubs:
                    action, base_state = self._miner._explore_near_hub(obs, state)
                else:
                    action, base_state = self._miner._explore(obs, state)
                state = self._copy_with_shared(replace(state,
                    wander_direction_index=base_state.wander_direction_index,
                    wander_steps_remaining=base_state.wander_steps_remaining,
                    last_mode=base_state.last_mode,
                    remembered_hub_row_from_spawn=base_state.remembered_hub_row_from_spawn,
                    remembered_hub_col_from_spawn=base_state.remembered_hub_col_from_spawn,
                    last_pos=base_state.last_pos,
                    last_move_target=base_state.last_move_target,
                ))
            elif state.known_hubs:
                action, base_state = self._aligner._explore_near_hub(obs, state)
                state = self._copy_with_shared(replace(state,
                    wander_direction_index=base_state.wander_direction_index,
                    wander_steps_remaining=base_state.wander_steps_remaining,
                    last_mode=base_state.last_mode,
                    last_pos=getattr(base_state, 'last_pos', state.last_pos),
                    last_move_target=getattr(base_state, 'last_move_target', state.last_move_target),
                ))
            else:
                action, base_state = self._aligner._explore(obs, state)
                state = self._copy_with_shared(replace(state,
                    wander_direction_index=base_state.wander_direction_index,
                    wander_steps_remaining=base_state.wander_steps_remaining,
                    last_mode=base_state.last_mode,
                    last_pos=getattr(base_state, 'last_pos', state.last_pos),
                    last_move_target=getattr(base_state, 'last_move_target', state.last_move_target),
                ))
            # Note: state already updated in each branch above — don't double-update below

        else:
            action, state = self._unstuck_move(state)

        state.skill_steps += 1
        action_name = action.name if hasattr(action, "name") else ""
        if action_name.startswith("move_"):
            direction = action_name[len("move_"):]
            delta_map = {"north": (-1, 0), "east": (0, 1), "south": (1, 0), "west": (0, -1)}
            dr, dc = delta_map.get(direction, (0, 0))
            state.last_move_target = (current_abs[0] + dr, current_abs[1] + dc)
        return action, state


class CrossRolePolicy(MultiAgentPolicy):
    """Policy where all agents can dynamically choose aligner or miner role."""

    short_names = ["cross_role", "machina_cross_role"]

    def __init__(
        self,
        policy_env_info: PolicyEnvInterface,
        device: str = "cpu",
        num_aligners: int | str = 3,
        return_load: int | str = 20,  # Issue-36 v7: reduced from 40 to 20 per issue #34 findings
        stuck_threshold: int | str = 20,
        unstuck_horizon: int | str = 4,
        llm_api_url: str | None = None,
        llm_model: str | None = "nvidia/llama-3.3-nemotron-super-49b-v1.5",
        llm_api_key_env: str = "OPENROUTER_API_KEY",
        llm_site_url: str | None = None,
        llm_app_name: str = "cogames-cross-role",
        llm_timeout_s: float | str = 10.0,
        llm_responder: Callable[[str], str] | None = None,
        llm_local_model_path: str | None = None,
        scripted_miners: bool | str = "auto",
    ):
        super().__init__(policy_env_info, device=device)
        n_agents = policy_env_info.num_agents
        sm_str = str(scripted_miners).lower()
        if sm_str == "auto":
            self._scripted_miners = n_agents >= 6
        else:
            self._scripted_miners = sm_str in ("true", "1", "yes")
        logger.info("CrossRolePolicy scripted_miners=%s (n_agents=%d, raw=%s)", self._scripted_miners, n_agents, scripted_miners)
        self._shared_map = SharedMap()
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
        self._num_aligners = int(num_aligners)
        self._return_load = int(return_load)
        self._stuck_threshold = int(stuck_threshold)
        self._unstuck_horizon = int(unstuck_horizon)
        self._agent_policies: dict[int, StatefulAgentPolicy[CrossRoleState]] = {}

    def agent_policy(self, agent_id: int) -> StatefulAgentPolicy[CrossRoleState]:
        if agent_id not in self._agent_policies:
            preferred = "aligner" if agent_id < self._num_aligners else "miner"
            # scripted_miners: miner-designated agents skip LLM calls entirely,
            # using only scripted fallback logic. This reduces concurrent API calls
            # from 8 to num_aligners, preventing BackoffLimitExceeded in qualifying.
            use_planner = self._planner
            if self._scripted_miners and preferred == "miner":
                use_planner = None
            impl = CrossRolePolicyImpl(
                self._policy_env_info,
                agent_id,
                planner=use_planner,
                stuck_threshold=self._stuck_threshold,
                unstuck_horizon=self._unstuck_horizon,
                return_load=self._return_load,
                shared_map=self._shared_map,
                preferred_initial_gear=preferred,
            )
            self._agent_policies[agent_id] = StatefulAgentPolicy(
                impl,
                self._policy_env_info,
                agent_id=agent_id,
            )
        return self._agent_policies[agent_id]


class GearTestPolicy(MultiAgentPolicy):
    """Two-phase gear test harness for issue-12 gear reliability experiments.

    Phase 1 (steps 0-phase_switch_step): agents acquire initial preferred gear.
    Phase 2 (steps phase_switch_step-episode_end): agents switch to opposite gear.

    Metrics (from GEAR_STATE log lines):
    - initial_gear_success_rate: fraction holding correct gear at step phase_switch_step
    - gear_change_success_rate: fraction holding switched gear at end
    - gear_contamination_rate: fraction holding scout/scrambler gear at end
    """

    short_names = ["gear_test"]

    def __init__(
        self,
        policy_env_info: PolicyEnvInterface,
        device: str = "cpu",
        num_aligners: int | str = 3,
        return_load: int | str = 40,
        stuck_threshold: int | str = 20,
        unstuck_horizon: int | str = 4,
        phase_switch_step: int | str = 200,
        llm_api_url: str | None = None,
        llm_model: str | None = "nvidia/llama-3.3-nemotron-super-49b-v1.5",
        llm_api_key_env: str = "OPENROUTER_API_KEY",
        llm_site_url: str | None = None,
        llm_app_name: str = "cogames-gear-test",
        llm_timeout_s: float | str = 10.0,
        llm_responder: Callable[[str], str] | None = None,
        llm_local_model_path: str | None = None,
    ):
        super().__init__(policy_env_info, device=device)
        self._shared_map = SharedMap()
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
        self._num_aligners = int(num_aligners)
        self._return_load = int(return_load)
        self._stuck_threshold = int(stuck_threshold)
        self._unstuck_horizon = int(unstuck_horizon)
        self._phase_switch_step = int(phase_switch_step)
        self._agent_policies: dict[int, StatefulAgentPolicy[CrossRoleState]] = {}

    def agent_policy(self, agent_id: int) -> StatefulAgentPolicy[CrossRoleState]:
        if agent_id not in self._agent_policies:
            preferred = "aligner" if agent_id < self._num_aligners else "miner"
            impl = CrossRolePolicyImpl(
                self._policy_env_info,
                agent_id,
                planner=self._planner,
                stuck_threshold=self._stuck_threshold,
                unstuck_horizon=self._unstuck_horizon,
                return_load=self._return_load,
                shared_map=self._shared_map,
                preferred_initial_gear=preferred,
                phase_switch_step=self._phase_switch_step,
            )
            self._agent_policies[agent_id] = StatefulAgentPolicy(
                impl,
                self._policy_env_info,
                agent_id=agent_id,
            )
        return self._agent_policies[agent_id]
