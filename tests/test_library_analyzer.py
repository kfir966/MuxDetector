import csv

from muxfind.cli import main
from muxfind.library_analyzer import LibraryAnalyzer


_MUX_CELL = '''
cell(MUX2) {
  pin(A) { direction : input; }
  pin(B) { direction : input; }
  pin(S) { direction : input; }
  pin(Y) { direction : output; function : "(!S&A)|(S&B)"; }
}
'''


def test_library_analyzer_reports_cell_and_pin_edge_cases(tmp_path):
    library = tmp_path / "edge_cases.lib"
    library.write_text(
        "library(test) {"
        + _MUX_CELL
        + '''
        cell(SEQ) {
          ff(IQ, IQN) { next_state : "D"; }
          pin(Q) { direction : output; function : D; }
        }
        cell(MISSING) {
          pin(Y) { direction : output; }
        }
        cell(MALFORMED) {
          pin(Y) { direction : output; function : "A &"; }
        }
        cell(NESTED) {
          test_cell(test) {
            pin(FAKE_TEST) { direction : output; function : "(!S&A)|(S&B)"; }
          }
          pg_pin(VDD) {
            pin(FAKE_POWER) { direction : output; function : "(!S&A)|(S&B)"; }
          }
        }
        }
        ''',
        encoding="utf-8",
    )

    result = LibraryAnalyzer(library, "not_mux").analyze()
    rows_by_cell = {row.cell: row for row in result.rows}

    assert rows_by_cell["MUX2"].classification == "MUX2"
    assert (rows_by_cell["SEQ"].output_pin, rows_by_cell["SEQ"].classification) == (
        "-",
        "SEQUENTIAL",
    )
    assert rows_by_cell["MISSING"].classification == "NO_FUNCTION"
    assert rows_by_cell["MALFORMED"].classification == "NO_FUNCTION"
    assert rows_by_cell["MALFORMED"].notes.startswith("expression parse error:")
    assert rows_by_cell["NESTED"].classification == "NO_FUNCTION"
    assert not {"FAKE_TEST", "FAKE_POWER"} & {
        row.output_pin for row in result.rows
    }


def test_library_analyzer_applies_both_tristate_policies(tmp_path):
    library = tmp_path / "tristate.lib"
    library.write_text(
        'library(test) { cell(TRI) {'
        ' pin(Y) { direction : output; three_state : OE;'
        ' function : "(!S&A)|(S&B)"; }'
        '} }',
        encoding="utf-8",
    )

    excluded = LibraryAnalyzer(library, "not_mux").analyze().rows[0]
    analyzed = LibraryAnalyzer(library, "function").analyze().rows[0]

    assert excluded.classification == "NOT_MUX"
    assert "tri-state output excluded" in excluded.notes
    assert analyzed.classification == "MUX2"
    assert "classified by function" in analyzed.notes


def test_cli_writes_expected_csv_columns_and_debug_summary(tmp_path, capsys):
    library = tmp_path / "mux.lib"
    output = tmp_path / "result.csv"
    library.write_text(f"library(test) {{{_MUX_CELL}}}", encoding="utf-8")

    assert main([str(library), "-o", str(output), "--debug"]) == 0

    with output.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.reader(handle))
    assert rows[0] == [
        "cell",
        "output_pin",
        "classification",
        "inverting",
        "select_pins",
        "data_pins",
        "notes",
    ]
    assert rows[1][:6] == ["MUX2", "Y", "MUX2", "no", "S", "A/B"]
    assert "MUX2=1" in capsys.readouterr().err


def test_cli_applies_function_tristate_policy(tmp_path, capsys):
    library = tmp_path / "tristate.lib"
    library.write_text(
        'library(test) { cell(TRI) {'
        ' pin(Y) { direction : output; three_state : OE;'
        ' function : "(!S&A)|(S&B)"; }'
        '} }',
        encoding="utf-8",
    )

    assert main([str(library), "--tristate-policy", "function"]) == 0

    rows = list(csv.reader(capsys.readouterr().out.splitlines()))
    assert rows[1] == [
        "TRI",
        "Y",
        "MUX2",
        "no",
        "S",
        "A/B",
        "tri-state present; classified by function",
    ]
