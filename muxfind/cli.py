"""Command-line interface for muxfind."""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from .boolean.mux_analysis_limit_error import MuxAnalysisLimitError
from .csv_writer import write_rows
from .library_analyzer import LibraryAnalyzer
from .results.analysis_result import AnalysisResult


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="muxfind",
        description="Detect functional MUXes in Liberty libraries",
    )
    parser.add_argument(
        "inputs",
        nargs="+",
        help="Plain or gzipped Liberty library paths",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="Output CSV path (default: stdout)",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Print result counts and elapsed time to stderr",
    )
    parser.add_argument(
        "--tristate-policy",
        choices=("not_mux", "function"),
        default="not_mux",
        help="How to classify tri-state outputs (default: not_mux)",
    )
    return parser


def _update_final_result(final_result: AnalysisResult, result: AnalysisResult) -> None:
    final_result.rows.extend(result.rows)
    for classification, count in result.count.items():
        final_result.count[classification] = (
            final_result.count.get(classification, 0) + count
        )


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    started = time.perf_counter()
    final_result = AnalysisResult()

    for input_path in args.inputs:
        library_analyzer = LibraryAnalyzer(input_path, args.tristate_policy)
        try:
            result = library_analyzer.analyze()
        except MuxAnalysisLimitError as exc:
            print(f"muxfind: {input_path}: {exc}", file=sys.stderr)
            return 2
        _update_final_result(final_result, result)

    if args.output:
        with args.output.open("w", encoding="utf-8", newline="") as output_file:
            write_rows(final_result.rows, output_file)
    else:
        write_rows(final_result.rows, sys.stdout)

    if args.debug:
        elapsed = time.perf_counter() - started
        summary = " ".join(
            f"{classification}={count}"
            for classification, count in final_result.count.items()
        )
        print(f"{summary} elapsed={elapsed:.3f}s", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
