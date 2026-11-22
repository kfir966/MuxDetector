"""One output row written to the result CSV."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CsvRow:
    """Represent one CSV result row."""

    cell: str
    output_pin: str
    classification: str
    inverting: str = ""
    select_pins: tuple[str, ...] = ()
    data_pins: tuple[str, ...] = ()
    notes: str = ""

    def to_csv_fields(self) -> list[str]:
        """Return the row values in CSV column order."""
        return [
            self.cell,
            self.output_pin,
            self.classification,
            self.inverting,
            "/".join(self.select_pins),
            "/".join(self.data_pins),
            self.notes,
        ]
