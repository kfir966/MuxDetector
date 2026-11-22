"""CSV output helpers."""

from __future__ import annotations

import csv
import sys
from typing import Iterable, TextIO

from .results.csv_row import CsvRow


COLUMNS = ["cell", "output_pin", "classification", "inverting", "select_pins", "data_pins", "notes"]


def write_rows(rows: Iterable[CsvRow], destination: TextIO = sys.stdout) -> None:
    writer = csv.writer(destination, lineterminator="\n")
    writer.writerow(COLUMNS)
    writer.writerows(row.to_csv_fields() for row in rows)
