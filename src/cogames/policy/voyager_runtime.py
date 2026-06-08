from __future__ import annotations

import ast
from dataclasses import dataclass
from typing import Any, Callable


_ALLOWED_BUILTINS = {
    "abs": abs,
    "bool": bool,
    "dict": dict,
    "float": float,
    "int": int,
    "len": len,
    "list": list,
    "max": max,
    "min": min,
    "range": range,
    "set": set,
    "str": str,
    "sum": sum,
}


@dataclass
class SkillResult:
    ok: bool
    action: Any | None
    next_state: dict[str, Any]
    error: str | None = None


class SkillRuntime:
    """Restricted runtime for generated Voyager skills."""

    def __init__(self) -> None:
        self._compiled_cache: dict[str, Callable[[Any, dict[str, Any]], Any]] = {}

    def validate_code(self, code: str) -> None:
        try:
            tree = ast.parse(code)
        except SyntaxError as exc:
            raise ValueError(f"invalid syntax: {exc.msg}") from exc

        has_step = False
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom, ast.With, ast.AsyncWith, ast.ClassDef, ast.Global, ast.Nonlocal, ast.Lambda)):
                raise ValueError(f"unsupported node: {type(node).__name__}")
            if isinstance(node, ast.FunctionDef) and node.name == "step":
                has_step = True
                if len(node.args.args) != 2:
                    raise ValueError("step must accept exactly (ctx, state)")

        if not has_step:
            raise ValueError("missing step(ctx, state) function")

    def _compile(self, code: str) -> Callable[[Any, dict[str, Any]], Any]:
        if code in self._compiled_cache:
            return self._compiled_cache[code]

        self.validate_code(code)
        globals_dict: dict[str, Any] = {"__builtins__": _ALLOWED_BUILTINS}
        locals_dict: dict[str, Any] = {}
        exec(compile(code, "<voyager-skill>", "exec"), globals_dict, locals_dict)

        step_fn = locals_dict.get("step")
        if not callable(step_fn):
            raise ValueError("step(ctx, state) was not defined")

        self._compiled_cache[code] = step_fn
        return step_fn

    def execute(self, code: str, ctx: Any, state: dict[str, Any] | None = None) -> SkillResult:
        state = dict(state or {})
        try:
            step_fn = self._compile(code)
            action = step_fn(ctx, state)
            if action is None:
                action = ctx.noop()
            return SkillResult(ok=True, action=action, next_state=state)
        except Exception as exc:
            return SkillResult(ok=False, action=ctx.noop(), next_state=state, error=f"{type(exc).__name__}: {exc}")
