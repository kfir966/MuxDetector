"""Lex and parse Liberty Boolean function strings."""

from __future__ import annotations

from .expression_parser_engine import ExpressionParser
from .expression_token import ExpressionToken
from .ast import Expression
from .expression_syntax_error import ExpressionSyntaxError


_OPERATORS = set("'!^*&+|()")
_INVALID_PUNCTUATION = set(",;{}")


def _is_constant(value: str) -> bool:
    """Return whether a token is a Liberty Boolean constant."""
    return value in ("0", "1")


def _tokenize_expression(text: str) -> list[ExpressionToken]:
    """Split an expression string into identifiers, constants, and operators."""
    tokens: list[ExpressionToken] = []
    position = 0

    while position < len(text):
        char = text[position]
        if char.isspace():
            position += 1
            continue
        if char in _OPERATORS:
            tokens.append(ExpressionToken("OPERATOR", char))
            position += 1
            continue
        if char == '"':
            value, position = _read_quoted_identifier(text, position)
            tokens.append(ExpressionToken("IDENTIFIER", value))
            continue
        if char in _INVALID_PUNCTUATION:
            raise ExpressionSyntaxError(f"unexpected character {char!r}")

        value, position = _read_identifier(text, position)
        kind = "CONSTANT" if _is_constant(value) else "IDENTIFIER"
        tokens.append(ExpressionToken(kind, value))
    return tokens


def _read_quoted_identifier(text: str, position: int) -> tuple[str, int]:
    """Read one quoted pin name, honoring escaped quotes and backslashes."""
    position += 1
    characters: list[str] = []
    while position < len(text):
        char = text[position]
        if char == '"':
            return "".join(characters), position + 1
        if char == "\\" and position + 1 < len(text):
            escaped = text[position + 1]
            if escaped in ('"', "\\"):
                characters.append(escaped)
            else:
                characters.extend((char, escaped))
            position += 2
        else:
            characters.append(char)
            position += 1
    raise ExpressionSyntaxError("unterminated quoted identifier")


def _read_identifier(text: str, position: int) -> tuple[str, int]:
    """Read an unquoted name, keeping bus brackets inside the identifier."""
    start = position
    bracket_depth = 0
    while position < len(text):
        char = text[position]
        if bracket_depth == 0 and (
            char.isspace() or char in _OPERATORS or char in _INVALID_PUNCTUATION
        ):
            break
        if char == "[":
            bracket_depth += 1
        elif char == "]":
            if bracket_depth == 0:
                raise ExpressionSyntaxError("unmatched closing bracket in identifier")
            bracket_depth -= 1
        position += 1

    if bracket_depth:
        raise ExpressionSyntaxError("unmatched opening bracket in identifier")
    if position == start:
        raise ExpressionSyntaxError(f"unexpected character {text[position]!r}")
    return text[start:position], position


def parse_expression(text: str) -> Expression:
    """Parse a Liberty Boolean function string into an expression tree."""
    if not text.strip():
        raise ExpressionSyntaxError("empty expression")
    return ExpressionParser(_tokenize_expression(text)).parse()
