from __future__ import annotations

from typing import Any


DEFAULT_ROLE_PROMPT = (
    "You are a CoGames policy assistant. Return Python code for a single function "
    "def step(ctx, state): that uses only the ctx API."
)


def build_voyager_prompt(
    *,
    observation_summary: str,
    assignment: str,
    previous_skill_code: str | None,
    recent_results: list[dict[str, Any]],
    role_prompt: str = DEFAULT_ROLE_PROMPT,
) -> str:
    """Build a compact prompt for API-first skill generation."""
    results_text = "\n".join(
        f"- ok={result.get('ok')} action={result.get('action')} error={result.get('error')}"
        for result in recent_results[-5:]
    )
    prev = previous_skill_code if previous_skill_code else "<none>"
    return (
        f"Role:\n{role_prompt}\n\n"
        f"Assignment:\n{assignment}\n\n"
        f"Observation:\n{observation_summary}\n\n"
        f"Previous skill:\n{prev}\n\n"
        f"Recent execution results:\n{results_text or '<none>'}\n\n"
        "Return either:\n"
        "1) Python code that defines step(ctx, state), or\n"
        "2) CONTINUE"
    )
