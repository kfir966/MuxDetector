"""Token type used by the private Boolean-expression lexer."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ExpressionToken:
    """Hold one Boolean-expression token and its source spelling."""

    kind: str
    value: str
