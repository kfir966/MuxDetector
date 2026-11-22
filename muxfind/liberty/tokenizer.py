"""Tokenize Liberty text into structural tokens."""

from __future__ import annotations

from io import StringIO

from .lex_error import LibertyLexError
from .token import LibertyToken


_SYMBOLS = r"{}()=;:,+-*^&|!'/"


def _strip_comments_and_continuations(text: str) -> str:
    """Remove comments and escaped line breaks outside quoted strings."""
    cleaned = StringIO()
    position = 0
    in_string = False
    escaped = False

    while position < len(text):
        char = text[position]
        if in_string:
            cleaned.write(char)
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            position += 1
            continue

        if text.startswith("/*", position):
            end = text.find("*/", position + 2)
            if end == -1:
                raise LibertyLexError("unterminated block comment")
            cleaned.write(" ")
            for comment_char in text[position:end + 2]:
                if comment_char in "\r\n":
                    cleaned.write(comment_char)
            position = end + 2
            continue

        if text.startswith("//", position):
            cleaned.write(" ")
            while position < len(text) and text[position] not in "\r\n":
                position += 1
            continue

        if char == '"':
            in_string = True
            cleaned.write(char)
            position += 1
            continue

        if char == "\\" and position + 1 < len(text) and text[position + 1] in "\r\n":
            cleaned.write(" ")
            position += 2
            if text[position - 1] == "\r" and position < len(text) and text[position] == "\n":
                position += 1
            continue

        cleaned.write(char)
        position += 1
    return cleaned.getvalue()


def _read_quoted_string(text: str, position: int) -> tuple[str, int]:
    """Read one quoted Liberty string and return its value and next position."""
    position += 1
    characters: list[str] = []
    while position < len(text):
        if text[position] == "\\" and position + 1 < len(text):
            characters.extend((text[position], text[position + 1]))
            position += 2
        elif text[position] == '"':
            return "".join(characters), position + 1
        else:
            characters.append(text[position])
            position += 1
    raise LibertyLexError("unterminated quoted string")


def tokenize_liberty(text: str) -> list[LibertyToken]:
    """Remove comments and tokenize identifiers, strings, and symbols."""
    text = _strip_comments_and_continuations(text)
    tokens: list[LibertyToken] = []
    position = 0

    while position < len(text):
        char = text[position]
        if char.isspace():
            position += 1
        elif char == '"':
            value, position = _read_quoted_string(text, position)
            tokens.append(LibertyToken("STRING", value))
        elif char in _SYMBOLS:
            tokens.append(LibertyToken("SYMBOL", char))
            position += 1
        else:
            start = position
            while (
                position < len(text)
                and not text[position].isspace()
                and text[position] not in _SYMBOLS + '"'
            ):
                position += 1
            tokens.append(LibertyToken("BAREWORD", text[start:position]))
    return tokens
