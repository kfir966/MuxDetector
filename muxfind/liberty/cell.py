"""Liberty cell model."""

from __future__ import annotations

from dataclasses import dataclass, field

from .output_pin import OutputPin


@dataclass
class Cell:
    """Store the cell properties needed by the analyzer."""

    name: str
    is_sequential: bool = False
    output_pins: list[OutputPin] = field(default_factory=list)
