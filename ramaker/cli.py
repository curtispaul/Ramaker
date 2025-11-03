"""Command line interface for the cemetery PDF-to-DXF pipeline."""
from __future__ import annotations

import argparse
import logging
import math
from pathlib import Path
from typing import Iterable, List

from .dxf_writer import add_linework, add_text_entities, create_dxf_document, save_dxf
from .geometry import group_segments_into_polylines, segments_from_polylines, snap_segment_angles
from .pdf_processor import (
    PageAnalysis,
    analyze_pdf,
    denormalize_segments,
    denormalize_text_positions,
    normalize_segments,
    normalize_text_positions,
)
from .text_processing import enrich_text_labels


LOGGER = logging.getLogger(__name__)


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Convert cemetery PDF maps into DXF linework")
    parser.add_argument("input", type=Path, help="Path to the input PDF map")
    parser.add_argument("output", type=Path, help="Destination DXF path")
    parser.add_argument("--dpi", type=int, default=300, help="Rasterization DPI when vector data is unavailable")
    parser.add_argument("--min-segment-length", type=float, default=5.0, help="Minimum line segment length in PDF units")
    parser.add_argument("--snap-angle", type=float, default=45.0, help="Angle snapping increment in degrees")
    parser.add_argument("--join-tolerance", type=float, default=6.0, help="Distance threshold in PDF units when chaining segments")
    parser.add_argument("--text-height", type=float, default=0.25, help="DXF text height in drawing units")
    parser.add_argument(
        "--debug-overlay",
        type=Path,
        help="Optional path to save a raster debug overlay image (requires Pillow)",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging verbosity",
    )
    return parser


def configure_logging(level: str) -> None:
    logging.basicConfig(level=getattr(logging, level), format="%(levelname)s: %(message)s")


def filter_segments_by_length(
    segments: Iterable[tuple[tuple[float, float], tuple[float, float]]],
    width: float,
    height: float,
    min_length: float,
):
    filtered: List[tuple[tuple[float, float], tuple[float, float]]] = []
    for (x0, y0), (x1, y1) in segments:
        length = math.hypot((x1 - x0) * width, (y1 - y0) * height)
        if length >= min_length:
            filtered.append(((x0, y0), (x1, y1)))
    return filtered


def process_analysis(analysis: PageAnalysis, args: argparse.Namespace) -> None:
    LOGGER.info("Processing page %s (%sx%s) vector=%s", analysis.page_number, analysis.width, analysis.height, analysis.vector_based)

    normalized_segments = normalize_segments(analysis.line_segments, analysis.width, analysis.height)
    filtered_segments = filter_segments_by_length(normalized_segments, analysis.width, analysis.height, args.min_segment_length)
    snapped_segments = snap_segment_angles(filtered_segments, snap_increment=args.snap_angle)
    join_tolerance = (
        args.join_tolerance / max(analysis.width, 1.0),
        args.join_tolerance / max(analysis.height, 1.0),
    )
    polylines = group_segments_into_polylines(snapped_segments, tolerance=join_tolerance)
    cleaned_segments = segments_from_polylines(polylines)

    normalized_texts = normalize_text_positions(analysis.texts, analysis.width, analysis.height)
    cleaned_texts = enrich_text_labels(normalized_texts)

    if LOGGER.isEnabledFor(logging.DEBUG):
        fonts = sorted({text.fontname for text in analysis.texts if text.fontname})
        LOGGER.debug("Page %s fonts detected: %s", analysis.page_number, fonts or "<none>")

    analysis.line_segments = denormalize_segments(cleaned_segments, analysis.width, analysis.height)
    analysis.texts = denormalize_text_positions(cleaned_texts, analysis.width, analysis.height)

    if args.debug_overlay and analysis.raster_debug_image is not None:
        overlay_path = args.debug_overlay
        if overlay_path.suffix:
            filename = f"{overlay_path.stem}_page_{analysis.page_number:03d}{overlay_path.suffix}"
        else:
            filename = f"{overlay_path.name}_page_{analysis.page_number:03d}.png"
        path = overlay_path.with_name(filename)
        LOGGER.info("Saving debug overlay to %s", path)
        path.parent.mkdir(parents=True, exist_ok=True)
        analysis.raster_debug_image.save(path)


def run_cli(argv: List[str] | None = None) -> int:
    parser = build_argument_parser()
    args = parser.parse_args(argv)
    configure_logging(args.log_level)

    analyses = analyze_pdf(str(args.input), dpi=args.dpi, collect_debug_images=bool(args.debug_overlay))

    doc = create_dxf_document()

    for analysis in analyses:
        process_analysis(analysis, args)
        add_linework(doc, analysis.line_segments)
        add_text_entities(doc, analysis.texts, text_height=args.text_height)

    save_dxf(doc, str(args.output))
    LOGGER.info("DXF saved to %s", args.output)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(run_cli())
