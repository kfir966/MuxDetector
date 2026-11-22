"""Classify Boolean functions as MUX2, MUX4, MUX8, or NOT_MUX."""

from __future__ import annotations

from collections.abc import Iterator

from .bdd import BDD
from .ast import BinOp, Const, Expression, Not, Var
from .mux_result import MuxResult


_VALID_ACTIVE_COUNTS = {3: 1, 6: 2, 11: 3}
_MAX_TRUTH_TABLE_VARIABLES = 16


def _postorder(root: Expression) -> Iterator[Expression]:
    """Yield child nodes before parents according to the calculation order.

    The parser can create long left-deep trees for a long series of operators.
    An explicit stack avoids hitting Python's recursion limit while walking them.
    """
    pending = [(root, False)]
    while pending:
        node, children_visited = pending.pop()
        if children_visited:
            yield node
        elif isinstance(node, Not):
            pending.extend(((node, True), (node.child, False)))
        elif isinstance(node, BinOp):
            pending.extend(((node, True), (node.right, False), (node.left, False)))
        elif not isinstance(node, (Const, Var)):
            raise TypeError(f"unsupported expression node {type(node).__name__}")
        else:
            yield node


def _collect_variables(expression: Expression) -> list[str]:
    """Collect distinct input names in the order they appear in the AST."""
    names: list[str] = []
    seen: set[str] = set()
    pending = [expression]
    while pending:
        node = pending.pop()
        if isinstance(node, Var):
            if node.name not in seen:
                seen.add(node.name)
                names.append(node.name)
        elif isinstance(node, Not):
            pending.append(node.child)
        elif isinstance(node, BinOp):
            pending.extend((node.right, node.left))
        elif not isinstance(node, Const):
            raise TypeError(f"unsupported expression node {type(node).__name__}")
    return names


def _create_variable_truth_table_masks(names: list[str]) -> tuple[dict[str, int], int]:
    """Build each input's truth-table column as an integer bit vector.

    For names ["A", "B", "C"], there are 8 rows. 
    A changes every row, B every two rows, C every four rows, and so on... 
    Bit n stores that input's value in row n, with row 0 in the rightmost bit. The result is:

        ({"A": 0b10101010, "B": 0b11001100, "C": 0b11110000}, 0b11111111)

    The final integer has one bit set for every row and is used to limit NOT
    operations to the truth-table rows.
    """
    row_count = 1 << len(names)
    masks: dict[str, int] = {}
    for variable_index, name in enumerate(names):
        block_width = 1 << variable_index
        one_block = (1 << block_width) - 1
        column = 0
        for block_start in range(block_width, row_count, block_width * 2):
            column |= one_block << block_start
        masks[name] = column
    return masks, (1 << row_count) - 1


def _calculate_node_operation(node: Expression, left: int, right: int) -> int:
    if node.op == "AND":
        return left & right
    elif node.op == "OR":
        return left | right
    elif node.op == "XOR":
        return left ^ right
    else:
        raise ValueError(f"unsupported Boolean operator {node.op!r}")

def _evaluate(
    expression: Expression,
    variable_masks: dict[str, int],
    all_rows_mask: int,
) -> int:
    """Evaluate every truth-table row together using integer bit operations.

    Return an integer with one output bit per truth-table row. For example,
    with two inputs there are four rows:

        expression = A AND (NOT B)
        variable_masks = {"A": 0b1010, "B": 0b1100}
        all_rows_mask = 0b1111
        result = _evaluate(expression, variable_masks, all_rows_mask)

    The result is 0b0010: only row 1 (A=1, B=0) is true.

    """
    values: dict[int, int] = {} # node_ID -> truth-table column
    for node in _postorder(expression):
        if isinstance(node, Const):
            value = all_rows_mask if node.value else 0
        elif isinstance(node, Var):
            value = variable_masks.get(node.name, 0)
        elif isinstance(node, Not):
            # Flip every truth-table row's bit (Boolean NOT).
            value = all_rows_mask ^ values[id(node.child)]
        elif isinstance(node, BinOp):
            left, right = values[id(node.left)], values[id(node.right)]
            value = _calculate_node_operation(node, left, right)
        else:
            raise TypeError(f"unsupported expression node {type(node).__name__}")
        values[id(node)] = value
    return values[id(expression)]


def _restrict_table_to_input_value(
    table: int,
    variable_index_to_be_fixed: int,
    variable_count: int,
    value_to_be_fixed: int,
) -> int:
    """Keep rows where one input has the fixed given value, packing the remaining rows.

    An input at index `i` stays at each value for `2 ** i` consecutive rows.
    Its 0 and 1 blocks repeat in pairs, so the loop visits each pair across all
    `2 ** variable_count` rows. It extracts the requested block from each pair
    and appends it to the smaller, restricted table.
    """
    total_row_count = 1 << variable_count
    block_width = 1 << variable_index_to_be_fixed
    block_pair_width = block_width * 2
    block_mask = (1 << block_width) - 1
    selected_offset = block_width if value_to_be_fixed else 0
    restricted_table = 0
    result_bit_index = 0
    # The loop shifts each selected block into the next position in restricted_table.
    for block_start in range(0, total_row_count, block_pair_width):
        selected_block = (
            table >> (block_start + selected_offset)
        ) & block_mask
        restricted_table |= selected_block << result_bit_index
        result_bit_index += block_width
    return restricted_table


def _create_restricted_table_mask(variable_count: int) -> int:
    """Create a mask with one bit for each row after fixing one input.
    The formula is cofactor rows = 2 ** (n - 1)
    Examples:
        1 input -> 1 remaining row -> 0b1
        2 inputs -> 2 remaining rows -> 0b11
        3 inputs -> 4 remaining rows -> 0b1111
        4 inputs -> 8 remaining rows -> 0b11111111
    """
    restricted_row_count = 1 << (variable_count - 1)
    return (1 << restricted_row_count) - 1


def _classify_role_for_variable_index(
    table: int,
    variable_index: int,
    variable_count: int,
    restricted_table_mask: int,
) -> str:
    """Classify one input as binate, positive, negative, or vacuous.
    `rising` mask keeps rows where low is 0 and high is 1 (0 to 1); 
    `falling` keeps rows where low is 1 and high is 0 (1 to 0). 
    """
    low = _restrict_table_to_input_value(table, variable_index, variable_count, 0)
    high = _restrict_table_to_input_value(table, variable_index, variable_count, 1)
    rising = (restricted_table_mask ^ low) & high
    falling = low & (restricted_table_mask ^ high)
    if rising and falling:
        return "binate"
    if rising:
        return "positive"
    if falling:
        return "negative"
    return "vacuous"


def _classify_variables(
    table: int,
    names: list[str],
) -> tuple[int, list[str], dict[str, str]]:
    """Drop vacuous variables and label the rest by their polarity."""
    if not names:
        return table, [], {}

    variable_count = len(names)
    restricted_table_mask = _create_restricted_table_mask(variable_count)
    roles: dict[str, str] = {}
    for variable_index, name in enumerate(names):
        roles[name] = _classify_role_for_variable_index(
            table,
            variable_index,
            variable_count,
            restricted_table_mask,
        )

    active = [name for name in names if roles[name] != "vacuous"]
    reduced = table
    remaining_count = variable_count
    # Remove vacuous columns right-to-left so the remaining indices stay valid.
    for index in range(variable_count - 1, -1, -1):
        if roles[names[index]] == "vacuous":
            reduced = _restrict_table_to_input_value(reduced, index, remaining_count, 0)
            remaining_count -= 1
    return reduced, active, {name: roles[name] for name in active}


def _bdd_support(expression: Expression, names: list[str]) -> list[str]:
    """Use a bounded BDD to discard irrelevant inputs before truth-table creation.

    A fixed variable order is needed so equivalent subgraphs can be shared.
    Variables use their first-appearance order in `names`. Each AST node is
    built from the BDDs of its already-visited children.
    """
    bdd = BDD()
    variable_indices = {name: index for index, name in enumerate(names)}
    bdd_nodes: dict[int, int] = {} # AST node ID -> BDD node ID
    for node in _postorder(expression):
        if isinstance(node, Const):
            bdd_node = bdd.make_constant_node(node.value)
        elif isinstance(node, Var):
            bdd_node = bdd.make_variable_node(variable_indices[node.name])
        elif isinstance(node, Not):
            bdd_node = bdd.negate_node(bdd_nodes[id(node.child)]) # children are visited before
        elif isinstance(node, BinOp):
            bdd_node = bdd.apply_operator(
                node.op,
                bdd_nodes[id(node.left)],
                bdd_nodes[id(node.right)],
            )
        else:
            raise TypeError(f"unsupported expression node {type(node).__name__}")
        bdd_nodes[id(node)] = bdd_node

    support = bdd.find_active_variables(bdd_nodes[id(expression)])
    return [name for index, name in enumerate(names) if index in support]


def _verify_mux_select_assignments(
    table: int,
    names: list[str],
    selects: list[str],
    data_names: list[str],
    inverted: bool,
) -> tuple[str, ...] | None:
    """
    Verify every select assignment maps to one data pin and return that order.
    steps:
    1. set select pins to a plausible value (0 or 1) and 
    2. restrict the truth table to those rows
    3. verifies the current settings truth table matches the data_input's expected table
    """
    select_indices = {name: names.index(name) for name in selects} # name -> index in names
    data_masks, data_rows_mask = _create_variable_truth_table_masks(data_names)
    ordered_data: list[str] = []
    already_matched_data_pins: set[str] = set()

    for select_value in range(1 << len(selects)):
        selected = sorted(
            (select_indices[name], (select_value >> bit) & 1) # (name's index, current value for that bit)
            for bit, name in enumerate(selects)
        )
        restricted_table = table
        remaining_count = len(names)
        # Restrict right-to-left; each removed variable shifts later indices.
        for index, value in reversed(selected):
            restricted_table = _restrict_table_to_input_value(
                restricted_table, index, remaining_count, value
            )
            remaining_count -= 1

        matches: list[str] = []
        for data_name in data_names:
            # expected is just that data_var per the relevant select combination
            expected = data_masks[data_name] 
            if inverted:
                expected ^= data_rows_mask
            if restricted_table == expected:
                matches.append(data_name)

        if len(matches) != 1 or matches[0] in already_matched_data_pins:
            return None
        ordered_data.append(matches[0])
        already_matched_data_pins.add(matches[0])

    return tuple(ordered_data) if set(ordered_data) == set(data_names) else None


def _create_mux_result(
    table: int,
    names: list[str],
    roles: dict[str, str],
) -> MuxResult:
    """Create the classification result from the table and input roles."""
    active_count = len(names)
    if active_count not in _VALID_ACTIVE_COUNTS:
        return MuxResult(
            "NOT_MUX",
            notes=f"active input count is {active_count}, not 3, 6, or 11",
        )

    select_count = _VALID_ACTIVE_COUNTS[active_count]
    selects = [name for name in names if roles[name] == "binate"]
    data_names = [name for name in names if roles[name] != "binate"]
    polarities = {roles[name] for name in data_names}  # set (positive + negative values)
    
    if len(selects) != select_count:
        return MuxResult("NOT_MUX", notes="wrong number of binate select inputs")
    if len(polarities) != 1 or not polarities <= {"positive", "negative"}:
        return MuxResult("NOT_MUX", notes="data inputs have mixed or invalid polarity")

    inverted = polarities == {"negative"}
    ordered_data = _verify_mux_select_assignments(
        table, names, selects, data_names, inverted
    )
    if ordered_data is None:
        return MuxResult(
            "NOT_MUX",
            notes="select assignments do not map one-to-one to data",
        )

    return MuxResult(
        classification=f"MUX{len(data_names)}",
        inverting="yes" if inverted else "no",
        select_pins=tuple(selects),
        data_pins=ordered_data,
    )


def analyze_expression(expression: Expression) -> MuxResult:
    """Classify one Boolean expression as MUX2/MUX4/MUX8 or NOT_MUX."""
    names = _collect_variables(expression)
    has_too_many_variables = len(names) > _MAX_TRUTH_TABLE_VARIABLES
    if has_too_many_variables:
        names = _bdd_support(expression, names)
        if len(names) not in _VALID_ACTIVE_COUNTS:
            return MuxResult(
                "NOT_MUX",
                notes=f"active input count is {len(names)}, not 3, 6, or 11",
            )

    variable_masks, all_rows_mask = _create_variable_truth_table_masks(names)
    table = _evaluate(expression, variable_masks, all_rows_mask)
    table, names, roles = _classify_variables(table, names) # also remove vacuos rows

    return _create_mux_result(table, names, roles)
