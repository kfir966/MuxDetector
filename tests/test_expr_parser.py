import pytest

from muxfind.boolean.ast import BinOp, Const, Not, Var
from muxfind.boolean.expression_parser import parse_expression
from muxfind.boolean.expression_syntax_error import ExpressionSyntaxError


def test_xor_has_higher_precedence_than_and():
    expression = parse_expression("A ^ B & C")

    assert expression == BinOp("AND", BinOp("XOR", Var("A"), Var("B")), Var("C"))


def test_and_has_higher_precedence_than_or():
    expression = parse_expression("A + B & C")

    assert expression == BinOp("OR", Var("A"), BinOp("AND", Var("B"), Var("C")))


def test_adjacency_means_and():
    expression = parse_expression("A B")

    assert expression == BinOp("AND", Var("A"), Var("B"))


def test_implicit_and_can_mix_with_explicit_and():
    expression = parse_expression("A B & C")

    assert expression == BinOp(
        "AND",
        BinOp("AND", Var("A"), Var("B")),
        Var("C"),
    )


def test_prefix_and_postfix_not():
    expression = parse_expression("!A'")

    assert expression == Not(Not(Var("A")))


def test_constants_and_quoted_bus_identifiers():
    expression = parse_expression('1 & "data pin" & D[0]')

    assert expression == BinOp(
        "AND",
        BinOp("AND", Const(1), Var("data pin")),
        Var("D[0]"),
    )


@pytest.mark.parametrize("text", ["", "A &", "(A + B", "A )", '"unfinished'])
def test_invalid_expressions_raise_syntax_error(text):
    with pytest.raises(ExpressionSyntaxError):
        parse_expression(text)
