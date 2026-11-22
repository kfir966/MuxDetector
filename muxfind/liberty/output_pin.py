"""Cell output-pin model."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class OutputPin:
    """Store the function-related attributes of a cell output pin."""

    name: str
    function: str | None
    three_state: str | None = None
