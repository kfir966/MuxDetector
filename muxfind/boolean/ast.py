"""Boolean expression tree node types."""

from __future__ import annotations

from dataclasses import dataclass

__all__ = ["BinOp", "Const", "Expression", "Not", "Var"]


class Expression:
    """Base type for values in a Boolean expression tree."""


@dataclass(frozen=True)
class Const(Expression):
    """Represent a Boolean constant leaf."""

    value: int


@dataclass(frozen=True)
class Var(Expression):
    """Represent a named Boolean input."""

    name: str


@dataclass(frozen=True)
class Not(Expression):
    """Represent logical negation of one expression."""

    child: Expression


@dataclass(frozen=True)
class BinOp(Expression):
    """Represent a binary Boolean operation and its two operands."""

    op: str
    left: Expression
    right: Expression
