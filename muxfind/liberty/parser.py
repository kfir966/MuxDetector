"""Parse Liberty structural tokens into cells and output pins."""

from __future__ import annotations

from .cell import Cell
from .output_pin import OutputPin
from .token import LibertyToken


_SEQUENTIAL_GROUPS = {"ff", "ff_bank", "latch", "latch_bank", "statetable"}


def _is_this_symbol(token: LibertyToken, value: str) -> bool:
    return token.kind == "SYMBOL" and token.value == value


def _find_matching_delimiter(
    tokens: list[LibertyToken],
    start: int,
    opening: str,
    closing: str,
    limit: int,
) -> int:
    """Find the matching closing delimiter before limit."""
    depth = 0
    for position in range(start, min(limit, len(tokens))):
        if _is_this_symbol(tokens[position], opening):
            depth += 1
        elif _is_this_symbol(tokens[position], closing):
            depth -= 1
            if depth == 0:
                return position
    return limit


def _group_body(
    tokens: list[LibertyToken],
    keyword_position: int,
    limit: int,
) -> tuple[int, int] | None:
    """Return a group's opening and closing braces, if its header is complete."""
    open_paren = keyword_position + 1
    if open_paren >= limit or not _is_this_symbol(tokens[open_paren], "("):
        return None
    close_paren = _find_matching_delimiter(tokens, open_paren, "(", ")", limit)
    open_brace = close_paren + 1
    if open_brace >= limit or not _is_this_symbol(tokens[open_brace], "{"):
        return None
    close_brace = _find_matching_delimiter(tokens, open_brace, "{", "}", limit)
    return open_brace, close_brace


def _name_from_args(
    tokens: list[LibertyToken],
    open_paren: int,
    close_paren: int,
) -> str | None:
    """Return the first argument from a group header."""
    values = [
        token.value
        for token in tokens[open_paren + 1:close_paren]
        if not (
            token.kind == "SYMBOL" and token.value in (",", ":", "=")
        )
    ]
    return values[0].strip() if values else None


def _expression_until_semicolon(
    tokens: list[LibertyToken],
    position: int,
    end: int,
) -> tuple[str | None, int]:
    """Read an attribute value up to its semicolon."""
    values: list[LibertyToken] = []
    while position < end:
        token = tokens[position]
        if _is_this_symbol(token, ";"):
            if len(values) == 1 and values[0].kind == "STRING":
                return values[0].value, position + 1
            expression = " ".join(value.value for value in values).strip() or None
            return expression, position + 1
        values.append(token)
        position += 1
    expression = " ".join(value.value for value in values).strip() or None
    return expression, position


def _parse_pin_attribute(
    tokens: list[LibertyToken],
    position: int,
    end: int,
) -> tuple[str, str | None, int] | None:
    """Parse one function, three_state, or direction attribute."""
    if tokens[position].kind != "BAREWORD":
        return None
    key = tokens[position].value.lower()
    if key not in ("function", "three_state", "direction"):
        return None
    if position + 1 >= end or not (
        _is_this_symbol(tokens[position + 1], "=")
        or _is_this_symbol(tokens[position + 1], ":")
    ):
        return None
    value, next_position = _expression_until_semicolon(tokens, position + 2, end)
    return key, value, next_position


def _parse_pin_block(
    tokens: list[LibertyToken],
    start: int,
    end: int,
    name: str,
) -> OutputPin | None:
    """Read function-related attributes and ignore input pins."""
    function: str | None = None
    three_state: str | None = None
    direction: str | None = None
    position = start
    while position < end:
        attribute = _parse_pin_attribute(tokens, position, end)
        if attribute is None:
            position += 1
            continue
        key, value, position = attribute
        if key == "function":
            function = value
        elif key == "three_state":
            three_state = value
        else:
            direction = value.lower() if value else None
    if direction == "input":
        return None
    return OutputPin(name=name, function=function, three_state=three_state)


def _skip_next_state_attribute(
    tokens: list[LibertyToken],
    position: int,
    end: int,
) -> int | None:
    """Skip a next-state attribute so its value is not parsed as cell structure."""
    if tokens[position].kind != "BAREWORD":
        return None
    if tokens[position].value.lower() not in ("next_state", "next_state_unmapped"):
        return None
    if position + 1 >= end or not (
        _is_this_symbol(tokens[position + 1], "=")
        or _is_this_symbol(tokens[position + 1], ":")
    ):
        return None
    _, next_position = _expression_until_semicolon(tokens, position + 2, end)
    return next_position


def _parse_pin_group(
    tokens: list[LibertyToken],
    position: int,
    end: int,
    cell: Cell,
) -> int:
    """Parse a direct pin group and return the first token after it."""
    body = _group_body(tokens, position, end)
    if body is None:
        return position + 1

    open_brace, close_brace = body
    open_paren = position + 1
    close_paren = _find_matching_delimiter(tokens, open_paren, "(", ")", end)
    pin_name = _name_from_args(tokens, open_paren, close_paren)
    if pin_name:
        output_pin = _parse_pin_block(tokens, open_brace + 1, close_brace, pin_name)
        if output_pin is not None:
            cell.output_pins.append(output_pin)
    return close_brace + 1


def _parse_cell_item(
    tokens: list[LibertyToken],
    position: int,
    end: int,
    cell: Cell,
) -> int:
    """Process one direct item in a cell and return the next token index."""
    name = (
        tokens[position].value.lower()
        if tokens[position].kind == "BAREWORD"
        else ""
    )
    if name in _SEQUENTIAL_GROUPS:
        cell.is_sequential = True

    next_state_position = _skip_next_state_attribute(tokens, position, end)
    if next_state_position is not None:
        return next_state_position

    if name == "pin":
        return _parse_pin_group(tokens, position, end, cell)

    # Other nested groups (such as timing, power, and bus groups) are not pins.
    body = _group_body(tokens, position, end)
    if body is not None:
        _, close_brace = body
        return close_brace + 1
    return position + 1


def _parse_cell_block(
    tokens: list[LibertyToken],
    open_brace: int,
    close_brace: int,
    name: str,
) -> Cell:
    """Parse direct cell attributes and pin groups, skipping nested groups."""
    cell = Cell(name=name)
    position = open_brace + 1
    while position < close_brace:
        position = _parse_cell_item(tokens, position, close_brace, cell)
    return cell


def _parse_cell_at(
    tokens: list[LibertyToken],
    position: int,
) -> tuple[Cell | None, int] | None:
    """Parse a cell group at position and return its next token index."""
    body = _group_body(tokens, position, len(tokens))
    if body is None:
        return None
    open_brace, close_brace = body
    open_paren = position + 1
    close_paren = _find_matching_delimiter(tokens, open_paren, "(", ")", len(tokens))
    name = _name_from_args(tokens, open_paren, close_paren)
    cell = _parse_cell_block(tokens, open_brace, close_brace, name) if name else None
    return cell, close_brace + 1


def parse_liberty(tokens: list[LibertyToken]) -> list[Cell]:
    """Parse structural tokens into cells."""
    cells: list[Cell] = []
    position = 0
    while position < len(tokens):
        if (
            tokens[position].kind == "BAREWORD"
            and tokens[position].value.lower() == "cell"
        ):
            parsed = _parse_cell_at(tokens, position)
            if parsed is not None:
                cell, position = parsed
                if cell is not None:
                    cells.append(cell)
                continue
        position += 1
    return cells
