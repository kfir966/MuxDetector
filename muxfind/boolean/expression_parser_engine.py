"""Recursive-descent parser implementation for Boolean expressions."""

from __future__ import annotations

from collections.abc import Callable

from .expression_token import ExpressionToken
from .ast import BinOp, Const, Expression, Not, Var
from .expression_syntax_error import ExpressionSyntaxError


class ExpressionParser:
    """Parse Boolean-expression tokens according to Liberty precedence."""

    def __init__(self, tokens: list[ExpressionToken]) -> None:
        self._tokens = tokens
        self._position = 0

    def parse(self) -> Expression:
        """Parse one complete expression and reject trailing tokens."""
        expression = self._parse_or()
        token = self._peek()
        if token is not None:
            raise ExpressionSyntaxError(f"unexpected token {token.value!r}")
        return expression

    def _is_relevant_operator(
        self,
        token: ExpressionToken | None,
        operators: dict[str, str],
    ) -> bool:
        """Check whether the next token is handled at this precedence level."""
        return token is not None and token.value in operators

    def _parse_or(self) -> Expression:
        """Parse OR, the lowest-precedence binary operator."""
        return self._parse_op(self._parse_and, {"+": "OR", "|": "OR"})

    def _parse_and(self) -> Expression:
        """Parse AND, including adjacency between neighboring operands."""
        left = self._parse_xor()

        while True:
            token = self._peek()
            if self._is_relevant_operator(token, {"&": "AND"}):
                self._take_and_advance()
                left = BinOp("AND", left, self._parse_xor())
            elif self._is_starts_implicit_and(token):
                left = self._parse_implicit_and(left)
            else:
                return left

    def _parse_xor(self) -> Expression:
        """Parse XOR more tightly than AND, as required by Liberty."""
        return self._parse_op(self._parse_unary, {"^": "XOR"})

    def _parse_op(
        self,
        parse_tighter_expression: Callable[[], Expression],
        operators: dict[str, str],
    ) -> Expression:
        """Parse a left-associative run at one precedence level."""
        left = parse_tighter_expression()

        while True:
            token = self._peek()
            if self._is_relevant_operator(token, operators):
                operator = self._take_and_advance().value
                right = parse_tighter_expression()
                left = BinOp(operators[operator], left, right)
            else:
                return left

    def _parse_implicit_and(self, left: Expression) -> Expression:
        """Join adjacent operands with AND when Liberty omits the operator."""
        return BinOp("AND", left, self._parse_xor())

    def _parse_unary(self) -> Expression:
        """Parse prefix NOT or continue to postfix NOT and primary syntax."""
        token = self._peek()
        if token is not None and token.value == "!":
            self._take_and_advance()
            return Not(self._parse_unary())
        return self._parse_postfix()

    def _parse_postfix(self) -> Expression:
        """Parse a primary expression followed by zero or more apostrophes."""
        expression = self._parse_primary()
        while (token := self._peek()) is not None and token.value == "'":
            self._take_and_advance()
            expression = Not(expression)
        return expression

    def _parse_primary(self) -> Expression:
        """Parse a constant, identifier, or parenthesized expression."""
        token = self._take_and_advance()
        if token.kind == "CONSTANT":
            return Const(int(token.value))
        if token.kind == "IDENTIFIER":
            return Var(token.value)
        if token.value == "(":
            expression = self._parse_or()
            closing = self._peek()
            if closing is None or closing.value != ")":
                raise ExpressionSyntaxError("missing closing parenthesis")
            self._take_and_advance()
            return expression
        raise ExpressionSyntaxError(f"unexpected token {token.value!r}")

    def _peek(self) -> ExpressionToken | None:
        """Return the next token without consuming it."""
        if self._position == len(self._tokens):
            return None
        return self._tokens[self._position]

    def _take_and_advance(self) -> ExpressionToken:
        """Consume and return the next token, or report unexpected end."""
        token = self._peek()
        if token is None:
            raise ExpressionSyntaxError("unexpected end of expression")
        self._position += 1
        return token

    @staticmethod
    def _is_starts_implicit_and(token: ExpressionToken | None) -> bool:
        """Check whether the next token can begin an implicitly ANDed operand."""
        return token is not None and (
            token.kind in ("IDENTIFIER", "CONSTANT") or token.value in ("(", "!")
        )
