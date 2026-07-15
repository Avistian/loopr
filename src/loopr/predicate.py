"""Safe predicate evaluation over a structured Result (see docs/adr/0006).

Handoff conditions are declared in loopr.yaml as small expressions like
``result.status == "issues"``. Loopr evaluates them itself — never an LLM — over a
restricted AST that permits only comparisons/boolean logic against ``result`` fields.
Anything else (calls, subscripts, other names) is rejected at parse time.
"""

from __future__ import annotations

import ast
from types import SimpleNamespace

from .result import Result

_ALLOWED_NODES = (
    ast.Expression,
    ast.BoolOp,
    ast.And,
    ast.Or,
    ast.UnaryOp,
    ast.Not,
    ast.Compare,
    ast.Eq,
    ast.NotEq,
    ast.Lt,
    ast.LtE,
    ast.Gt,
    ast.GtE,
    ast.In,
    ast.NotIn,
    ast.Name,
    ast.Load,
    ast.Attribute,
    ast.Constant,
    ast.List,
    ast.Tuple,
)

_RESULT_FIELDS = {"status", "summary", "next", "artifacts"}


class PredicateError(Exception):
    """Raised when a predicate is syntactically invalid or uses disallowed constructs."""


def compile_predicate(expr: str):
    try:
        tree = ast.parse(expr, mode="eval")
    except SyntaxError as exc:
        raise PredicateError(f"invalid predicate {expr!r}: {exc}") from exc

    for node in ast.walk(tree):
        if not isinstance(node, _ALLOWED_NODES):
            raise PredicateError(
                f"disallowed expression in predicate {expr!r}: {type(node).__name__}"
            )
        if isinstance(node, ast.Name) and node.id != "result":
            raise PredicateError(
                f"unknown name {node.id!r} in predicate {expr!r}; only 'result' is allowed"
            )
        if isinstance(node, ast.Attribute):
            if not (isinstance(node.value, ast.Name) and node.value.id == "result"):
                raise PredicateError(
                    f"predicate {expr!r}: attributes are only allowed on 'result'"
                )
            if node.attr not in _RESULT_FIELDS:
                raise PredicateError(
                    f"predicate {expr!r}: unknown result field {node.attr!r}"
                )
    return compile(tree, "<predicate>", "eval")


def evaluate_predicate(expr: str, result: Result) -> bool:
    """Evaluate ``expr`` against a Result. Raises PredicateError on invalid input."""
    code = compile_predicate(expr)
    namespace = SimpleNamespace(
        status=result.status,
        summary=result.summary,
        next=result.next,
        artifacts=result.artifacts,
    )
    return bool(eval(code, {"__builtins__": {}}, {"result": namespace}))
