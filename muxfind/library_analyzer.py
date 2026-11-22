"""Coordinate analysis of one Liberty library."""

from __future__ import annotations

from pathlib import Path

from .boolean.expression_parser import parse_expression
from .boolean.expression_syntax_error import ExpressionSyntaxError
from .boolean.mux_analyzer import analyze_expression
from .liberty.cell import Cell
from .liberty.output_pin import OutputPin
from .liberty.parser import parse_liberty
from .liberty.tokenizer import tokenize_liberty
from .results.analysis_result import AnalysisResult
from .results.csv_row import CsvRow
from .reader import read_text


class LibraryAnalyzer:
    def __init__(self, input_path: str | Path, tristate_policy: str) -> None:
        self.input_path = Path(input_path)
        self.tristate_policy = tristate_policy

    def analyze(self) -> AnalysisResult:
        text = read_text(self.input_path)
        tokens = tokenize_liberty(text)
        cells = parse_liberty(tokens)
        result = AnalysisResult()
        for cell in cells:
            for row in self._analyze_cell(cell):
                result.add_row(row)
        return result

    def _analyze_cell(self, cell: Cell) -> list[CsvRow]:
        if cell.is_sequential:
            return [CsvRow(cell.name, "-", "SEQUENTIAL")]
        if not cell.output_pins:
            return [CsvRow(
                cell.name,
                "-",
                "NO_FUNCTION",
                notes="no output pin or function",
            )]
        return [self._analyze_pin(cell, pin) for pin in cell.output_pins]

    def _analyze_pin(self, cell: Cell, pin: OutputPin) -> CsvRow:
        if pin.three_state and self.tristate_policy == "not_mux":
            return CsvRow(
                cell.name,
                pin.name,
                "NOT_MUX",
                notes="tri-state output excluded by policy",
            )
        if pin.function is None:
            return CsvRow(
                cell.name,
                pin.name,
                "NO_FUNCTION",
                notes="missing or unusable function",
            )

        try:
            result = analyze_expression(parse_expression(pin.function))
        except ExpressionSyntaxError as exc:
            return CsvRow(
                cell.name,
                pin.name,
                "NO_FUNCTION",
                notes=f"expression parse error: {exc}",
            )

        notes = result.notes
        if pin.three_state and self.tristate_policy == "function":
            notes = "; ".join(filter(
                None,
                (notes, "tri-state present; classified by function"),
            ))
        return CsvRow(
            cell=cell.name,
            output_pin=pin.name,
            classification=result.classification,
            inverting=result.inverting,
            select_pins=tuple(result.select_pins or ()),
            data_pins=tuple(result.data_pins or ()),
            notes=notes,
        )
