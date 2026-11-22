from pathlib import Path

from muxfind.library_analyzer import LibraryAnalyzer


_FIXTURE = Path(__file__).parent / "fixtures" / "liberty_end_to_end.lib"


def test_custom_liberty_fixture_classifies_each_case(request, capsys):
    result = LibraryAnalyzer(_FIXTURE, "not_mux").analyze()
    rows = {(row.cell, row.output_pin): row for row in result.rows}

    expected_classifications = {
        ("CASE_NORMAL_MUX2", "Y"): ("MUX2", "no"),
        ("CASE_INVERTED_MUX2", "Y"): ("MUX2", "yes"),
        ("CASE_MUX4", "Y"): ("MUX4", "no"),
        ("CASE_MUX8", "Y"): ("MUX8", "no"),
        ("CASE_GATED", "Y"): ("NOT_MUX", ""),
        ("CASE_MIXED_POLARITY", "Y"): ("NOT_MUX", ""),
        ("CASE_DUMMY_INPUT", "Y"): ("MUX2", "no"),
        ("CASE_REPEATED_DATA", "Y"): ("NOT_MUX", ""),
        ("CASE_MALFORMED", "Y"): ("NO_FUNCTION", ""),
        ("CASE_MISSING_FUNCTION", "Y"): ("NO_FUNCTION", ""),
        ("CASE_CONSTANT", "Y"): ("NOT_MUX", ""),
        ("CASE_SEQUENTIAL", "-"): ("SEQUENTIAL", ""),
        ("CASE_TRI_STATE", "Y"): ("NOT_MUX", ""),
        ("CASE_NESTED_GROUPS", "Y"): ("NOT_MUX", ""),
        ("CASE_QUOTED)", "Y)"): ("NOT_MUX", ""),
        ("CASE_TWO_OUTPUTS", "Y"): ("MUX2", "no"),
        ("CASE_TWO_OUTPUTS", "YN"): ("MUX2", "yes"),
    }

    if request.config.getoption("--show-expected-actual"):
        with capsys.disabled():
            print("Expected vs actual cell analysis:")
            for key in sorted(set(expected_classifications) | set(rows)):
                expected = expected_classifications.get(key)
                expected_text = (
                    f"{expected[0]}/{expected[1] or '-'}"
                    if expected is not None
                    else "unexpected cell/output"
                )
                row = rows.get(key)
                if row is None:
                    actual_text = "missing cell/output"
                else:
                    actual_text = (
                        f"{row.classification}/{row.inverting or '-'}"
                    )
                    if row.select_pins:
                        actual_text += f"; selects={','.join(row.select_pins)}"
                    if row.data_pins:
                        actual_text += f"; data={','.join(row.data_pins)}"
                    if row.notes:
                        actual_text += f"; note={row.notes}"
                print(
                    f"{key[0]}/{key[1]}: expected {expected_text}; "
                    f"actual {actual_text}"
                )

    assert set(rows) == set(expected_classifications)
    assert {
        key: (row.classification, row.inverting)
        for key, row in rows.items()
    } == expected_classifications

    assert rows[("CASE_MUX4", "Y")].select_pins == ("S0", "S1")
    assert rows[("CASE_MUX4", "Y")].data_pins == ("D0", "D1", "D2", "D3")
    assert rows[("CASE_MUX8", "Y")].select_pins == ("S0", "S1", "S2")
    assert rows[("CASE_MUX8", "Y")].data_pins == tuple(
        f"D{index}" for index in range(8)
    )
    assert rows[("CASE_MALFORMED", "Y")].notes.startswith(
        "expression parse error:"
    )
    assert not {"FAKE_TEST", "FAKE_POWER"} & {
        row.output_pin for row in rows.values()
    }


def test_custom_liberty_fixture_can_analyze_tri_state_function():
    result = LibraryAnalyzer(_FIXTURE, "function").analyze()
    tri_state_row = next(
        row for row in result.rows if row.cell == "CASE_TRI_STATE"
    )

    assert tri_state_row.classification == "MUX2"
    assert "classified by function" in tri_state_row.notes


def test_reader_and_analyzer_handle_1000_simple_cells(tmp_path):
    library = tmp_path / "generated_1000_cells.lib"
    with library.open("w", encoding="utf-8", newline="\n") as output:
        output.write("library(generated) {\n")
        for index in range(1000):
            output.write(
                f"cell(CELL_{index:04}) {{ "
                "pin(A) { direction : input; } "
                "pin(Y) { direction : output; function : A; } "
                "}\n"
            )
        output.write("}\n")

    result = LibraryAnalyzer(library, "not_mux").analyze()

    assert len(result.rows) == 1000
    assert result.rows[0].cell == "CELL_0000"
    assert result.rows[-1].cell == "CELL_0999"
    assert all(row.classification == "NOT_MUX" for row in result.rows)
