import pytest

from muxfind.boolean.ast import BinOp, Const, Expression, Not, Var
from muxfind.boolean.mux_analysis_limit_error import MuxAnalysisLimitError
from muxfind.boolean.mux_analyzer import analyze_expression


def _and(expressions: list[Expression]) -> Expression:
    result = expressions[0]
    for expression in expressions[1:]:
        result = BinOp("AND", result, expression)
    return result


def _or(expressions: list[Expression]) -> Expression:
    result = expressions[0]
    for expression in expressions[1:]:
        result = BinOp("OR", result, expression)
    return result


def _make_mux(
    select_count: int,
    inverted_data_indices: set[int] | None = None,
) -> Expression:
    """Create a MUX AST whose select index 0 is its least-significant bit."""
    inverted_data_indices = inverted_data_indices or set()
    select_pins = [f"S{index}" for index in range(select_count)]
    data_pins = [f"D{index}" for index in range(1 << select_count)]
    terms = []

    for selected_value, data_pin in enumerate(data_pins):
        term = [
            Var(pin) if selected_value & (1 << index) else Not(Var(pin))
            for index, pin in enumerate(select_pins)
        ]
        data_value: Expression = Var(data_pin)
        if selected_value in inverted_data_indices:
            data_value = Not(data_value)
        terms.append(_and([*term, data_value]))

    return _or(terms)


@pytest.mark.parametrize("select_count", [1, 2, 3])
@pytest.mark.parametrize("inverted", [False, True])
def test_classifies_mux_sizes_and_data_polarity(select_count, inverted):
    inverted_indices = set(range(1 << select_count)) if inverted else set()

    result = analyze_expression(_make_mux(select_count, inverted_indices))

    assert result.classification == f"MUX{1 << select_count}"
    assert result.inverting == ("yes" if inverted else "no")
    assert result.select_pins == tuple(f"S{index}" for index in range(select_count))
    assert result.data_pins == tuple(f"D{index}" for index in range(1 << select_count))


def test_removes_vacuous_inputs_even_with_more_than_truth_table_limit():
    expression = _make_mux(1)
    for index in range(20):
        dummy = Var(f"X{index}")
        expression = BinOp(
            "OR",
            expression,
            BinOp("AND", dummy, Not(dummy)),
        )

    result = analyze_expression(expression)

    assert result.classification == "MUX2"


def test_high_fanin_constant_expression_has_no_active_inputs():
    expression: Expression = Const(1)
    for index in range(20):
        expression = BinOp("OR", expression, Var(f"X{index}"))

    result = analyze_expression(expression)

    assert result.classification == "NOT_MUX"
    assert "active input count is 0" in result.notes


def test_rejects_function_with_invalid_select_data_mapping():
    terms = []
    for selected_value in range(4):
        select_term = [
            Var(f"S{index}") if selected_value & (1 << index)
            else Not(Var(f"S{index}"))
            for index in range(2)
        ]
        data: Expression = Var(f"D{selected_value}")
        if selected_value == 0:
            data = BinOp("AND", data, Var("D1"))
        terms.append(_and([*select_term, data]))
    expression = _or(terms)

    result = analyze_expression(expression)

    assert result.classification == "NOT_MUX"
    assert "select assignments" in result.notes


def test_rejects_mixed_data_polarity():
    result = analyze_expression(_make_mux(1, {0}))

    assert result.classification == "NOT_MUX"
    assert "polarity" in result.notes


def test_constant_expression_is_not_a_mux():
    result = analyze_expression(Const(1))

    assert result.classification == "NOT_MUX"


def test_reports_limit_for_too_many_symbolic_variables():
    expression: Expression = Var("X0")
    for index in range(1, 129):
        expression = BinOp("AND", expression, Var(f"X{index}"))

    with pytest.raises(MuxAnalysisLimitError, match="limited to 128 variables"):
        analyze_expression(expression)
