from muxfind.boolean.bdd import BDD


def test_public_bdd_operations_reduce_a_contradiction():
    bdd = BDD()
    variable = bdd.make_variable_node(0)
    opposite = bdd.negate_node(variable)

    contradiction = bdd.apply_operator("AND", variable, opposite)

    assert contradiction == bdd.make_constant_node(0)
    assert bdd.find_active_variables(contradiction) == set()


def test_decision_node_ids_start_at_zero():
    bdd = BDD()

    assert bdd.make_variable_node(0) == 0
    assert bdd.make_constant_node(0) < 0
    assert bdd.make_constant_node(1) < 0


def test_bdd_removes_an_input_that_cannot_affect_the_result():
    bdd = BDD()
    first_input = bdd.make_variable_node(0)
    irrelevant_input = bdd.make_variable_node(1)
    always_true = bdd.apply_operator(
        "OR", irrelevant_input, bdd.negate_node(irrelevant_input)
    )

    result = bdd.apply_operator("AND", first_input, always_true)

    assert bdd.find_active_variables(result) == {0}
