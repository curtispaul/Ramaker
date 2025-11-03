"""DXF export utilities for cemetery map geometry."""
from __future__ import annotations

from pathlib import Path
from typing import Iterable

import logging

try:
    import ezdxf
except Exception as exc:  # pragma: no cover - optional dependency
    ezdxf = None  # type: ignore
    logging.getLogger(__name__).warning("ezdxf is not available: %s", exc)

from .geometry import Polyline
from .pdf_processor import Segment, TextElement


def create_dxf_document() -> "ezdxf.EzDxf":  # type: ignore[name-defined]
    if ezdxf is None:
        raise RuntimeError("ezdxf is required to generate DXF files")
    doc = ezdxf.new("R2010")
    if "LINES" not in doc.layers:
        doc.layers.new(name="LINES")
    if "TEXT" not in doc.layers:
        doc.layers.new(name="TEXT")
    return doc


def add_linework(doc: "ezdxf.EzDxf", segments: Iterable[Segment], layer: str = "LINES") -> None:  # type: ignore[name-defined]
    msp = doc.modelspace()
    for (x0, y0), (x1, y1) in segments:
        msp.add_line((x0, y0), (x1, y1), dxfattribs={"layer": layer})


def add_polylines(doc: "ezdxf.EzDxf", polylines: Iterable[Polyline], layer: str = "LINES") -> None:  # type: ignore[name-defined]
    msp = doc.modelspace()
    for polyline in polylines:
        if len(polyline.points) < 2:
            continue
        msp.add_polyline2d(polyline.points, dxfattribs={"layer": layer})


def add_text_entities(doc: "ezdxf.EzDxf", texts: Iterable[TextElement], text_height: float = 0.2, layer: str = "TEXT") -> None:  # type: ignore[name-defined]
    msp = doc.modelspace()
    for text in texts:
        msp.add_text(text.value or "?", dxfattribs={"height": text_height, "layer": layer}).set_pos(text.position)


def save_dxf(doc: "ezdxf.EzDxf", output_path: str) -> Path:  # type: ignore[name-defined]
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    doc.saveas(path)
    return path
