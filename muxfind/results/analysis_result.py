"""Aggregate output rows and their classification counts."""

from __future__ import annotations

from dataclasses import dataclass, field

from .csv_row import CsvRow


@dataclass
class AnalysisResult:
    """Collect rows and count each classification."""

    rows: list[CsvRow] = field(default_factory=list)
    count: dict[str, int] = field(default_factory=lambda: {
        "MUX2": 0,
        "MUX4": 0,
        "MUX8": 0,
        "NOT_MUX": 0,
        "SEQUENTIAL": 0,
        "NO_FUNCTION": 0,
    })

    def add_row(self, row: CsvRow) -> None:
        """Append a row and increment its classification count."""
        self.rows.append(row)
        self.count[row.classification] = self.count.get(row.classification, 0) + 1
