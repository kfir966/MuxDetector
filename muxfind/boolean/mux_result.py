"""Result of classifying one Boolean expression."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MuxResult:
    """Hold the classification and pin mapping for one Boolean function."""

    classification: str
    inverting: str = ""
    select_pins: tuple[str, ...] = ()
    data_pins: tuple[str, ...] = ()
    notes: str = ""
