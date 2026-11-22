"""Liberty tokenizer output."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LibertyToken:
    """Represent one structural token from Liberty text."""

    kind: str
    value: str
