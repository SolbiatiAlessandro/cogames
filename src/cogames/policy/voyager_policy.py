from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

import httpx

from cogames.policy.starter_agent import StarterCogPolicyImpl, StarterCogState
from cogames.policy.voyager_prompt import build_voyager_prompt
from cogames.policy.voyager_runtime import SkillRuntime
from mettagrid.policy.policy import MultiAgentPolicy, StatefulAgentPolicy, StatefulPolicyImpl
from mettagrid.policy.policy_env_interface import PolicyEnvInterface
from mettagrid.simulator import Action
from mettagrid.simulator.interface import AgentObservation


@dataclass
class VoyagerAgentState:
    skill_code: str | None = None
    skill_state: dict[str, Any] = field(default_factory=dict)
    failure_count: int = 0
    recent_results: list[dict[str, Any]] = field(default_factory=list)
    fallback_state: StarterCogState = field(default_factory=StarterCogState)


class LLMClient:
    def __init__(
        self,
        api_url: str | None = None,
        timeout_s: float = 5.0,
        responder: Callable[[str], str] | None = None,
    ) -> None:
        self._api_url = api_url
        self._timeout_s = timeout_s
        self._responder = responder

    def generate(self, prompt: str) -> str:
        if self._responder is not None:
            return self._responder(prompt)

        if not self._api_url:
            raise RuntimeError("LLM client is not configured")

        with httpx.Client(timeout=self._timeout_s) as client:
            response = client.post(self._api_url, json={"prompt": prompt})
            response.raise_for_status()
            payload = response.json()
        text = payload.get("text")
        if not isinstance(text, str) or not text.strip():
            raise RuntimeError("LLM response missing non-empty 'text'")
        return text


class _VoyagerContext:
    def __init__(self, obs: AgentObservation, action_names: list[str], center: tuple[int, int]):
        self._obs = obs
        self._action_names = set(action_names)
        self._center = center

    def noop(self) -> Action:
        return Action(name="noop" if "noop" in self._action_names else next(iter(self._action_names)))

    def inventory(self) -> set[str]:
        items: set[str] = set()
        for token in self._obs.tokens:
            if token.location != self._center:
                continue
            name = token.feature.name
            if name.startswith("inv:"):
                parts = name.split(":", 2)
                if len(parts) >= 2:
                    items.add(parts[1])
        return items

    def has_item(self, name: str) -> bool:
        return name in self.inventory()

    def move_toward(self, target: tuple[int, int] | None) -> Action:
        if target is None:
            return self.noop()
        delta_row = target[0] - self._center[0]
        delta_col = target[1] - self._center[1]
        if abs(delta_row) >= abs(delta_col):
            direction = "south" if delta_row > 0 else "north"
        else:
            direction = "east" if delta_col > 0 else "west"
        action_name = f"move_{direction}"
        if action_name in self._action_names:
            return Action(name=action_name)
        return self.noop()


class VoyagerPolicyImpl(StatefulPolicyImpl[VoyagerAgentState]):
    def __init__(
        self,
        policy_env_info: PolicyEnvInterface,
        agent_id: int,
        llm_client: LLMClient,
        runtime: SkillRuntime,
        assignment: str,
        max_failures: int,
    ) -> None:
        self._policy_env_info = policy_env_info
        self._agent_id = agent_id
        self._llm_client = llm_client
        self._runtime = runtime
        self._assignment = assignment
        self._max_failures = max_failures
        self._fallback = StarterCogPolicyImpl(policy_env_info, agent_id)

    def initial_agent_state(self) -> VoyagerAgentState:
        return VoyagerAgentState()

    def _observation_summary(self, obs: AgentObservation) -> str:
        return f"agent={obs.agent_id} tokens={len(obs.tokens)}"

    def _fetch_skill(self, obs: AgentObservation, state: VoyagerAgentState) -> str | None:
        prompt = build_voyager_prompt(
            observation_summary=self._observation_summary(obs),
            assignment=self._assignment,
            previous_skill_code=state.skill_code,
            recent_results=state.recent_results,
        )
        text = self._llm_client.generate(prompt)
        if text.strip().upper() == "CONTINUE":
            return state.skill_code
        return text

    def _fallback_step(self, obs: AgentObservation, state: VoyagerAgentState) -> tuple[Action, VoyagerAgentState]:
        action, fallback_state = self._fallback.step_with_state(obs, state.fallback_state)
        state.fallback_state = fallback_state
        return action, state

    def step_with_state(self, obs: AgentObservation, state: VoyagerAgentState) -> tuple[Action, VoyagerAgentState]:
        if state.skill_code is None:
            try:
                state.skill_code = self._fetch_skill(obs, state)
            except Exception as exc:
                state.recent_results.append({"ok": False, "action": None, "error": str(exc)})
                return self._fallback_step(obs, state)

        if not state.skill_code:
            return self._fallback_step(obs, state)

        ctx = _VoyagerContext(
            obs=obs,
            action_names=self._policy_env_info.action_names,
            center=(self._policy_env_info.obs_height // 2, self._policy_env_info.obs_width // 2),
        )
        result = self._runtime.execute(state.skill_code, ctx, state.skill_state)
        state.skill_state = result.next_state
        state.recent_results.append(
            {"ok": result.ok, "action": getattr(result.action, "name", str(result.action)), "error": result.error}
        )

        if result.ok:
            state.failure_count = 0
            return result.action, state

        state.failure_count += 1
        if state.failure_count >= self._max_failures:
            state.skill_code = None
            state.skill_state = {}
            return self._fallback_step(obs, state)

        try:
            state.skill_code = self._fetch_skill(obs, state)
        except Exception:
            return self._fallback_step(obs, state)

        return self._fallback_step(obs, state)


class VoyagerPolicy(MultiAgentPolicy):
    short_names = ["voyager"]

    def __init__(
        self,
        policy_env_info: PolicyEnvInterface,
        device: str = "cpu",
        assignment: str = "Collect resources safely and return them to hubs.",
        max_failures: int = 2,
        llm_api_url: str | None = None,
        llm_responder: Callable[[str], str] | None = None,
    ):
        super().__init__(policy_env_info, device=device)
        self._assignment = assignment
        self._max_failures = max_failures
        self._runtime = SkillRuntime()
        self._llm_client = LLMClient(api_url=llm_api_url, responder=llm_responder)
        self._agent_policies: dict[int, StatefulAgentPolicy[VoyagerAgentState]] = {}

    def agent_policy(self, agent_id: int) -> StatefulAgentPolicy[VoyagerAgentState]:
        if agent_id not in self._agent_policies:
            impl = VoyagerPolicyImpl(
                policy_env_info=self._policy_env_info,
                agent_id=agent_id,
                llm_client=self._llm_client,
                runtime=self._runtime,
                assignment=self._assignment,
                max_failures=self._max_failures,
            )
            self._agent_policies[agent_id] = StatefulAgentPolicy(impl, self._policy_env_info, agent_id=agent_id)
        return self._agent_policies[agent_id]
