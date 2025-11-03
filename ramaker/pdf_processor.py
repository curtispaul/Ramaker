"""Utilities for inspecting and extracting geometry/text from cemetery PDF maps."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, List, Optional, Sequence, Tuple

import logging

try:
    import fitz  # PyMuPDF
except Exception as exc:  # pragma: no cover - import guard for optional dependency
    fitz = None  # type: ignore
    logging.getLogger(__name__).warning("PyMuPDF (fitz) is not available: %s", exc)

try:
    import pdfplumber
except Exception as exc:  # pragma: no cover - import guard for optional dependency
    pdfplumber = None  # type: ignore
    logging.getLogger(__name__).warning("pdfplumber is not available: %s", exc)

try:
    import cv2  # type: ignore
    import numpy as np
except Exception as exc:  # pragma: no cover - import guard for optional dependency
    cv2 = None  # type: ignore
    np = None  # type: ignore
    logging.getLogger(__name__).warning("OpenCV or NumPy is not available: %s", exc)

try:
    from PIL import Image
except Exception as exc:  # pragma: no cover - import guard for optional dependency
    Image = None  # type: ignore
    logging.getLogger(__name__).warning("Pillow is not available: %s", exc)


Point = Tuple[float, float]
Segment = Tuple[Point, Point]


@dataclass
class TextElement:
    """Represents a text item extracted from the map."""

    value: str
    position: Point
    fontname: Optional[str] = None
    size: Optional[float] = None


@dataclass
class PageAnalysis:
    """Container for the extracted geometry and text from a single PDF page."""

    page_number: int
    width: float
    height: float
    vector_based: bool
    line_segments: List[Segment] = field(default_factory=list)
    texts: List[TextElement] = field(default_factory=list)
    raster_debug_image: Optional[Image.Image] = None


def _iter_pdf_lines(page: "fitz.Page") -> Iterable[Segment]:
    """Yield raw line segments from vector drawing commands."""

    for drawing in page.get_drawings():
        for item in drawing["items"]:
            if item[0] == "l":
                _, points = item
                p0 = (points[0], page.rect.height - points[1])
                p1 = (points[2], page.rect.height - points[3])
                yield (p0, p1)
            elif item[0] == "re":
                # rectangles are reported as (x0, y0, x1, y1)
                _, (x0, y0, x1, y1) = item
                y0 = page.rect.height - y0
                y1 = page.rect.height - y1
                rect_segments = [
                    ((x0, y0), (x1, y0)),
                    ((x1, y0), (x1, y1)),
                    ((x1, y1), (x0, y1)),
                    ((x0, y1), (x0, y0)),
                ]
                yield from rect_segments


def _iter_pdf_text(page: "fitz.Page") -> Iterable[TextElement]:
    text_dict = page.get_text("dict")
    for block in text_dict.get("blocks", []):
        if block.get("type") != 0:
            continue
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                y = page.rect.height - span["bbox"][1]
                x = span["bbox"][0]
                yield TextElement(
                    value=span.get("text", ""),
                    position=(x, y),
                    fontname=span.get("font"),
                    size=span.get("size"),
                )


def _rasterize_page(page: "fitz.Page", dpi: int) -> Optional["np.ndarray"]:
    if cv2 is None or np is None:
        return None
    matrix = fitz.Matrix(dpi / 72.0, dpi / 72.0)
    pix = page.get_pixmap(matrix=matrix, alpha=False)
    image = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
    if pix.n == 4:
        image = image[:, :, :3]
    return image


def _detect_lines_raster(image: "np.ndarray", min_length: int = 40, max_gap: int = 10) -> List[Segment]:
    if cv2 is None or np is None:
        return []
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 50, 150, apertureSize=3)
    lines = cv2.HoughLinesP(edges, rho=1, theta=np.pi / 180, threshold=100, minLineLength=min_length, maxLineGap=max_gap)
    segments: List[Segment] = []
    if lines is None:
        return segments
    height, _ = gray.shape
    for x1, y1, x2, y2 in lines[:, 0]:
        p0 = (float(x1), float(height - y1))
        p1 = (float(x2), float(height - y2))
        segments.append((p0, p1))
    return segments


def _extract_text_raster(image: "np.ndarray") -> List[TextElement]:
    if cv2 is None or np is None:
        return []
    try:
        import pytesseract
    except Exception:  # pragma: no cover - optional dependency
        return []
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    ocr_result = pytesseract.image_to_data(gray, output_type=pytesseract.Output.DICT)
    height, _ = gray.shape
    texts: List[TextElement] = []
    for text, conf, x, y, w, h in zip(
        ocr_result["text"],
        ocr_result["conf"],
        ocr_result["left"],
        ocr_result["top"],
        ocr_result["width"],
        ocr_result["height"],
    ):
        if not text.strip():
            continue
        try:
            confidence = float(conf)
        except ValueError:
            confidence = -1.0
        if confidence < 0:
            continue
        cx = x + w / 2.0
        cy = height - (y + h / 2.0)
        texts.append(TextElement(value=text, position=(cx, cy)))
    return texts


def analyze_pdf(
    path: str,
    dpi: int = 300,
    use_pdfplumber: bool = True,
    collect_debug_images: bool = False,
) -> List[PageAnalysis]:
    """Analyze each page of the PDF and extract geometry and text.

    Args:
        path: Input PDF path.
        dpi: Resolution used when rasterizing for OCR/line detection.
        use_pdfplumber: If True and pdfplumber is available, inspect raw objects to
            double-check whether the page contains vector paths.
        collect_debug_images: Save rasterized images for optional visualization overlays.
    """

    if fitz is None:
        raise RuntimeError("PyMuPDF (fitz) is required to analyze PDF files")

    doc = fitz.open(path)
    plumber_doc = None
    if use_pdfplumber and pdfplumber is not None:
        try:
            plumber_doc = pdfplumber.open(path)
        except Exception as exc:
            logging.getLogger(__name__).debug("pdfplumber open failed: %s", exc)
            plumber_doc = None

    analyses: List[PageAnalysis] = []

    for page_index, page in enumerate(doc, start=1):
        width = float(page.rect.width)
        height = float(page.rect.height)

        vector_segments = list(_iter_pdf_lines(page))
        text_elements = list(_iter_pdf_text(page))
        vector_based = bool(vector_segments)

        if plumber_doc is not None:
            try:
                plumber_page = plumber_doc.pages[page_index - 1]
                if plumber_page.objects.get("line"):
                    vector_based = True
            except Exception as exc:
                logging.getLogger(__name__).debug("pdfplumber inspection failed on page %s: %s", page_index, exc)

        raster_segments: List[Segment] = []
        raster_texts: List[TextElement] = []
        debug_image: Optional[Image.Image] = None

        if not vector_based or cv2 is not None:
            raster_image = _rasterize_page(page, dpi)
            if raster_image is not None:
                raster_segments = _detect_lines_raster(raster_image)
                raster_texts = _extract_text_raster(raster_image)
                if collect_debug_images and Image is not None:
                    debug_image = Image.fromarray(raster_image)

        combined_segments = vector_segments or raster_segments
        combined_texts = text_elements or raster_texts

        analyses.append(
            PageAnalysis(
                page_number=page_index,
                width=width,
                height=height,
                vector_based=vector_based,
                line_segments=combined_segments,
                texts=combined_texts,
                raster_debug_image=debug_image,
            )
        )

    if plumber_doc is not None:
        plumber_doc.close()
    doc.close()

    return analyses


def normalize_segments(segments: Sequence[Segment], width: float, height: float) -> List[Segment]:
    """Normalize PDF coordinates to a 0..1 x/y domain."""

    normalized: List[Segment] = []
    if width == 0 or height == 0:
        return normalized
    for (x0, y0), (x1, y1) in segments:
        normalized.append(((x0 / width, y0 / height), (x1 / width, y1 / height)))
    return normalized


def normalize_text_positions(texts: Sequence[TextElement], width: float, height: float) -> List[TextElement]:
    normalized: List[TextElement] = []
    if width == 0 or height == 0:
        return normalized
    for text in texts:
        x, y = text.position
        normalized.append(
            TextElement(
                value=text.value,
                position=(x / width, y / height),
                fontname=text.fontname,
                size=text.size,
            )
        )
    return normalized


def denormalize_segments(segments: Sequence[Segment], width: float, height: float) -> List[Segment]:
    denormalized: List[Segment] = []
    for (x0, y0), (x1, y1) in segments:
        denormalized.append(((x0 * width, y0 * height), (x1 * width, y1 * height)))
    return denormalized


def denormalize_text_positions(texts: Sequence[TextElement], width: float, height: float) -> List[TextElement]:
    denormalized: List[TextElement] = []
    for text in texts:
        x, y = text.position
        denormalized.append(
            TextElement(
                value=text.value,
                position=(x * width, y * height),
                fontname=text.fontname,
                size=text.size,
            )
        )
    return denormalized
