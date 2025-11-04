"""Command line entry point for the cemetery PDF to DXF converter."""
from __future__ import annotations

import argparse
from pathlib import Path

from .pipeline import Pipeline, PipelineConfig


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Convert cemetery PDF maps into DXF files with LINES and TEXT layers.",
    )
    parser.add_argument(
        "input",
        type=Path,
        help="Path to the input cemetery map PDF.",
    )
    parser.add_argument(
        "output",
        type=Path,
        help="Destination path for the generated DXF file.",
    )
    parser.add_argument(
        "--min-line-length",
        type=float,
        default=2.0,
        help="Minimum length (in PDF units) for line segments to be kept.",
    )
    parser.add_argument(
        "--ocr",
        action="store_true",
        help="Enable OCR fallback using Tesseract for PDFs without embedded text.",
    )
    return parser


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = build_parser()
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    config = PipelineConfig(min_line_length=args.min_line_length, ocr=args.ocr)
    pipeline = Pipeline(config=config)
    pipeline.run(args.input, args.output)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
