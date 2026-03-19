import pytest

from cogames.policy.voyager_prompt import build_voyager_prompt
from cogames.policy.voyager_runtime import SkillRuntime


def test_build_prompt_contains_core_sections() -> None:
    prompt = build_voyager_prompt(
        observation_summary="agent=0 tokens=3",
        assignment="Collect resources",
        previous_skill_code="def step(ctx, state):\n    return ctx.noop()",
        recent_results=[{"ok": True, "action": "noop", "error": None}],
    )

    assert "Assignment:" in prompt
    assert "Observation:" in prompt
    assert "Previous skill:" in prompt
    assert "Recent execution results:" in prompt


def test_runtime_rejects_imports() -> None:
    runtime = SkillRuntime()
    bad_code = "import os\ndef step(ctx, state):\n    return ctx.noop()"

    with pytest.raises(ValueError, match="unsupported node"):
        runtime.validate_code(bad_code)


def test_runtime_executes_valid_skill() -> None:
    runtime = SkillRuntime()

    class Ctx:
        def noop(self) -> str:
            return "noop"

    result = runtime.execute(
        "def step(ctx, state):\n    state['count'] = state.get('count', 0) + 1\n    return ctx.noop()",
        Ctx(),
        {},
    )

    assert result.ok is True
    assert result.action == "noop"
    assert result.next_state["count"] == 1


def test_runtime_surfaces_exception_feedback() -> None:
    runtime = SkillRuntime()

    class Ctx:
        def noop(self) -> str:
            return "noop"

    result = runtime.execute("def step(ctx, state):\n    raise RuntimeError('boom')", Ctx(), {})

    assert result.ok is False
    assert result.action == "noop"
    assert "RuntimeError" in (result.error or "")


def test_policy_integration_behaviors() -> None:
    pytest.importorskip("mettagrid")

    from cogames.policy.voyager_policy import LLMClient, VoyagerPolicy
    from mettagrid.config.mettagrid_config import MettaGridConfig
    from mettagrid.policy.policy_env_interface import PolicyEnvInterface
    from mettagrid.simulator import Action, AgentObservation

    cfg = MettaGridConfig.EmptyRoom(num_agents=1, width=3, height=3, with_walls=False)
    env_info = PolicyEnvInterface.from_mg_cfg(cfg)

    failing = VoyagerPolicy(env_info, llm_responder=lambda _prompt: (_ for _ in ()).throw(RuntimeError("api down")))
    failing_agent = failing.agent_policy(0)
    obs = AgentObservation(agent_id=0, tokens=[])
    fallback_action = failing_agent.step(obs)

    assert isinstance(fallback_action, Action)
    assert fallback_action.name in env_info.action_names

    responses = iter(
        [
            "def step(ctx, state):\n    raise RuntimeError('bad')",
            "def step(ctx, state):\n    return ctx.noop()",
        ]
    )

    policy = VoyagerPolicy(env_info, llm_responder=lambda _prompt: next(responses), max_failures=5)
    agent = policy.agent_policy(0)

    first = agent.step(obs)
    second = agent.step(obs)

    assert first.name in env_info.action_names
    assert second.name == "noop"

    client = LLMClient(responder=lambda prompt: f"echo:{len(prompt)}")
    assert client.generate("hello").startswith("echo:")
