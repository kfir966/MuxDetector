"""Transparent plain/gzip text reader."""

from __future__ import annotations

import gzip
from pathlib import Path


def read_text(path: str | Path) -> str:
    """Read a plain or gzip-compressed text file into one string."""
    source = Path(path)
    opener = gzip.open if source.suffix.lower() == ".gz" else open
    with opener(source, "rt", encoding="utf-8", errors="replace") as handle:
        return handle.read()
