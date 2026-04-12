"""Setup script: monkey-patch cross_role_policy to remove retry-with-sleep loop.

The installed version of CrossRolePolicyImpl._plan_skill has a 3-retry loop
with time.sleep(3*attempt) that causes BackoffLimitExceeded in 8-agent qualifying.
This script patches it to use single-attempt + graceful scripted fallback.
"""
import importlib
import logging
import time

logger = logging.getLogger("setup_patch")


def apply_patch():
    try:
        mod = importlib.import_module("cogames.policy.cross_role_policy")
    except ImportError:
        logger.warning("cross_role_policy not found, skipping patch")
        return

    cls = mod.CrossRolePolicyImpl
    original_plan = cls._plan_skill

    # Check if already patched (our version doesn't have retry loop)
    import inspect
    source = inspect.getsource(original_plan)
    if "for attempt in range" not in source:
        logger.info("_plan_skill already patched (no retry loop found)")
        return

    logger.info("Patching _plan_skill to remove retry-with-sleep loop")

    def _patched_plan_skill(self, obs, state):
        """Patched _plan_skill: single LLM attempt, no retry-with-sleep."""
        gear = self._current_gear(obs)
        has_heart = self._inventory_count(obs, "heart") > 0
        carried = self._carried_total(obs)
        known_alignable = self._known_alignable_junctions(state)

        # Update shared gear tracking
        if self._shared_map is not None and hasattr(self._shared_map, "agent_gears"):
            self._shared_map.agent_gears[obs.agent_id] = gear

        effective_preferred = state.phase_preferred_gear or self._preferred_initial_gear

        # Bootstrap gear acquisition (same as original)
        contaminated = gear in ("scrambler", "scout")
        needs_gear_up = effective_preferred and (
            contaminated
            or (
                not state.gear_up_completed
                and (
                    gear == "none"
                    or (state.phase == 2 and gear != effective_preferred and gear in ("aligner", "miner"))
                )
            )
        )
        if contaminated and state.gear_up_completed:
            state.gear_up_completed = False
            state.gear_up_failures = 0
            self._event(state, f"contamination detected ({gear}): resetting gear_up state")
        if needs_gear_up:
            failures = state.gear_up_failures
            if failures == 0:
                bootstrap_gear = effective_preferred
                reason = f"phase{state.phase} gear target: {bootstrap_gear} (attempt 1)"
            elif failures == 1:
                bootstrap_gear = "miner" if effective_preferred == "aligner" else "aligner"
                reason = f"phase{state.phase} fallback gear: {bootstrap_gear}"
            elif state.phase == 2:
                bootstrap_gear = effective_preferred
                reason = f"phase2 persistent retry: {bootstrap_gear} (attempt {failures + 1})"
            else:
                bootstrap_gear = ""

            if bootstrap_gear:
                skill = f"gear_up_{bootstrap_gear}"
                if skill in mod.CROSS_ROLE_SKILLS:
                    state.current_skill = skill
                    state.current_reason = reason
                    state.skill_steps = 0
                    state.no_move_steps = 0
                    state.no_progress_on_target_steps = 0
                    self._event(state, f"planner selected {skill}: {reason}")
                    return

        team_aligners, team_miners = self._team_gear_counts()
        team_size = max(1, len(self._shared_map.agent_gears) if self._shared_map and hasattr(self._shared_map, "agent_gears") else 8)

        if state.get_heart_cooldown_steps > 0:
            state.get_heart_cooldown_steps -= 1
        hub_hearts_used = self._shared_map.hub_hearts_withdrawn if self._shared_map else 0
        hub_hard_depleted = False
        hub_on_cooldown = state.get_heart_cooldown_steps > 0
        hub_depleted = hub_on_cooldown

        # PATCHED: Single LLM attempt, no retry-with-sleep
        text = ""
        if self._planner is not None:
            prompt = mod.build_cross_role_prompt(
                current_gear=gear,
                has_heart=has_heart,
                carried_resources=carried,
                return_load=self._return_load,
                hub_visible=self._hub_visible(obs),
                known_hubs=len(state.known_hubs),
                known_neutral_junctions=len(state.known_neutral_junctions),
                known_friendly_junctions=len(state.known_friendly_junctions),
                known_enemy_junctions=len(state.known_enemy_junctions),
                known_extractors=len(state.known_extractors),
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
            started_at = time.perf_counter()
            try:
                text = self._planner.complete(prompt)
            except Exception as exc:
                latency_ms = (time.perf_counter() - started_at) * 1000.0
                logger.warning("agent=%s LLM error (%.1fms): %s", obs.agent_id, latency_ms, exc)
            else:
                latency_ms = (time.perf_counter() - started_at) * 1000.0
        else:
            pass  # scripted-only mode

        skill, reason = mod._parse_cross_role_skill(text)
        was_stuck = bool(
            state.recent_events and (
                "exited as stuck" in state.recent_events[-1]
                or "exited as stale" in state.recent_events[-1]
                or "timed out after" in state.recent_events[-1]
            )
        )

        # Scripted fallback
        if skill is None:
            if gear == "none":
                if was_stuck:
                    skill = "explore"
                else:
                    skill = "gear_up_aligner" if len(known_alignable) >= len(state.known_extractors) else "gear_up_miner"
            elif gear == "aligner":
                if was_stuck:
                    skill = "explore"
                elif hub_depleted and not has_heart:
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
                elif was_stuck:
                    skill = "explore"
                elif state.known_extractors:
                    skill = "mine_until_full"
                else:
                    skill = "explore"
            else:
                skill = "explore"
            reason = f"scripted fallback ({reason})"

        # Precondition enforcement (same as original)
        if skill == "get_heart" and hub_depleted and not has_heart:
            skill = "explore"
            reason = f"overrode get_heart: hub cooldown"
        if skill == "get_heart" and gear != "aligner":
            skill = "gear_up_aligner"
            reason = f"overrode to gear_up_aligner: need aligner gear"
        if skill == "align_neutral" and gear != "aligner":
            skill = "gear_up_aligner"
            reason = f"overrode to gear_up_aligner: need aligner gear"
        if skill == "align_neutral" and gear == "aligner" and not has_heart:
            if hub_depleted:
                skill = "explore"
                reason = "no heart and hub depleted"
            else:
                skill = "get_heart"
                reason = "need heart for align_neutral"
        if skill == "align_neutral" and gear == "aligner" and has_heart and not known_alignable:
            skill = "explore"
            reason = "no alignable junctions"
        if gear == "aligner" and has_heart and known_alignable and skill in {"explore", "get_heart"}:
            skill = "align_neutral"
            reason = f"overrode to align_neutral: have heart + {len(known_alignable)} targets"
        if skill == "mine_until_full" and gear != "miner":
            skill = "gear_up_miner"
            reason = f"overrode to gear_up_miner: need miner gear"
        if skill == "deposit_to_hub" and gear != "miner":
            skill = "gear_up_miner"
            reason = f"overrode to gear_up_miner: need miner gear"
        if skill == "deposit_to_hub" and gear == "miner" and carried == 0:
            skill = "mine_until_full" if state.known_extractors else "explore"
            reason = "no cargo to deposit"
        if skill == "gear_up_aligner" and gear == "aligner":
            if has_heart and known_alignable:
                skill = "align_neutral"
            elif not has_heart and hub_depleted:
                skill = "explore"
            elif not has_heart and state.known_hubs:
                skill = "get_heart"
            else:
                skill = "explore"
            reason = "already have aligner gear"
        if skill == "gear_up_miner" and gear == "miner":
            if carried >= self._return_load:
                skill = "deposit_to_hub"
            elif state.known_extractors:
                skill = "mine_until_full"
            else:
                skill = "explore"
            reason = "already have miner gear"

        if skill == "unstuck":
            state.consecutive_unstuck += 1
        else:
            state.consecutive_unstuck = 0
        if state.consecutive_unstuck >= 2:
            skill = "explore"
            reason = "overrode unstuck to explore"
            state.consecutive_unstuck = 0

        if skill in {"explore", "gear_up_aligner", "gear_up_miner"}:
            state.explore_start_junctions = len(state.known_neutral_junctions)
            state.explore_start_extractors = len(state.known_extractors)

        state.current_skill = skill
        state.current_reason = reason
        state.skill_steps = 0
        state.no_move_steps = 0
        state.no_progress_on_target_steps = 0
        self._event(state, f"planner selected {skill}: {reason}")

    cls._plan_skill = _patched_plan_skill
    logger.info("Successfully patched CrossRolePolicyImpl._plan_skill")


apply_patch()
