"""Core conversion pipeline for turning cemetery PDF maps into DXF layers."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Sequence, Tuple


@dataclass
class LineEntity:
    """Represents a straight line segment in PDF coordinates."""

    start: Tuple[float, float]
    end: Tuple[float, float]


@dataclass
class TextEntity:
    """Represents a text snippet extracted from the PDF."""

    value: str
    position: Tuple[float, float]
    height: float


@dataclass
class PipelineConfig:
    """Configuration controlling extraction heuristics."""

    min_line_length: float = 2.0
    ocr: bool = False


class Pipeline:
    """Extracts line work and text from a PDF file and writes a DXF file."""

    def __init__(self, config: PipelineConfig | None = None) -> None:
        self.config = config or PipelineConfig()

    def run(self, input_pdf: Path | str, output_dxf: Path | str) -> None:
        """Execute the conversion."""

        input_path = Path(input_pdf)
        if not input_path.exists():
            raise FileNotFoundError(f"Input PDF does not exist: {input_path}")

        lines, texts = self._extract_entities(input_path)
        self._write_dxf(output_dxf, lines, texts)

    # ------------------------------------------------------------------
    def _extract_entities(
        self, input_path: Path
    ) -> Tuple[List[LineEntity], List[TextEntity]]:
        try:
            import fitz  # type: ignore
        except ImportError as exc:  # pragma: no cover - dependency hint
            raise RuntimeError(
                "PyMuPDF (fitz) is required for vector extraction. Install it via 'pip install pymupdf'."
            ) from exc

        document = fitz.open(input_path)
        lines: List[LineEntity] = []
        texts: List[TextEntity] = []

        for page_index, page in enumerate(document):
            page_height = float(page.rect.height)
            lines.extend(self._extract_lines_from_page(page, page_height))
            texts.extend(self._extract_text_from_page(page, page_height))
            if self.config.ocr:
                texts.extend(self._ocr_page(page, page_height))

        return lines, texts

    def _extract_lines_from_page(self, page, page_height: float) -> List[LineEntity]:
        """Extract vector lines from the page drawings."""

        lines: List[LineEntity] = []
        for drawing in page.get_drawings():
            for item in drawing["items"]:
                operator = item[0]
                if operator == "l":  # line segment
                    start = self._transform_point(item[1], page_height)
                    end = self._transform_point(item[2], page_height)
                    if self._is_long_enough(start, end):
                        lines.append(LineEntity(start=start, end=end))
                elif operator == "re":  # rectangle -> four lines
                    x0, y0, x1, y1 = item[1]
                    p1 = self._transform_point((x0, y0), page_height)
                    p2 = self._transform_point((x1, y0), page_height)
                    p3 = self._transform_point((x1, y1), page_height)
                    p4 = self._transform_point((x0, y1), page_height)
                    rect_segments = [(p1, p2), (p2, p3), (p3, p4), (p4, p1)]
                    for start, end in rect_segments:
                        if self._is_long_enough(start, end):
                            lines.append(LineEntity(start=start, end=end))
                elif operator == "c":
                    # curves are ignored for now; they can be approximated with polylines later
                    continue
        return lines

    def _extract_text_from_page(self, page, page_height: float) -> List[TextEntity]:
        """Pull text blocks embedded in the PDF page."""

        blocks = page.get_text("blocks")
        texts: List[TextEntity] = []
        for block in blocks:
            x0, y0, x1, y1, text, block_no, block_type = block
            if block_type != 0:
                continue
            cleaned = text.strip()
            if not cleaned:
                continue
            center = ((x0 + x1) / 2.0, (y0 + y1) / 2.0)
            transformed_center = self._transform_point(center, page_height)
            height = max(abs(y1 - y0), 1.0)
            texts.append(
                TextEntity(value=cleaned, position=transformed_center, height=height)
            )
        return texts

    def _ocr_page(self, page, page_height: float) -> List[TextEntity]:
        """Optional OCR step when the PDF lacks embedded text."""

        try:
            import pytesseract
            from PIL import Image
        except ImportError as exc:  # pragma: no cover - dependency hint
            raise RuntimeError(
                "OCR requested but pytesseract and Pillow are not installed."
            ) from exc

        pix = page.get_pixmap()
        image = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        ocr_data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)
        texts: List[TextEntity] = []
        for i in range(len(ocr_data["text"])):
            raw_text = ocr_data["text"][i].strip()
            if not raw_text:
                continue
            x = ocr_data["left"][i] + ocr_data["width"][i] / 2
            y = ocr_data["top"][i] + ocr_data["height"][i] / 2
            position = self._transform_point((x, y), page_height)
            height = float(ocr_data["height"][i])
            texts.append(TextEntity(value=raw_text, position=position, height=height))
        return texts

    def _write_dxf(
        self,
        output_path: Path | str,
        lines: Sequence[LineEntity],
        texts: Sequence[TextEntity],
    ) -> None:
        try:
            import ezdxf
        except ImportError as exc:  # pragma: no cover - dependency hint
            raise RuntimeError(
                "The ezdxf package is required to write DXF files. Install it via 'pip install ezdxf'."
            ) from exc

        doc = ezdxf.new("R2010")
        if "LINES" not in doc.layers:
            doc.layers.add("LINES")
        if "TEXT" not in doc.layers:
            doc.layers.add("TEXT")

        msp = doc.modelspace()
        for line in lines:
            msp.add_line(line.start, line.end, dxfattribs={"layer": "LINES"})
        for text in texts:
            msp.add_text(
                text.value,
                dxfattribs={
                    "layer": "TEXT",
                    "height": max(text.height, 1.0),
                },
            ).set_pos(text.position)

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        doc.saveas(output_path)

    # ------------------------------------------------------------------
    def _transform_point(self, point: Tuple[float, float], page_height: float) -> Tuple[float, float]:
        x, y = point
        return float(x), float(page_height - y)

    def _is_long_enough(
        self, start: Tuple[float, float], end: Tuple[float, float]
    ) -> bool:
        dx = start[0] - end[0]
        dy = start[1] - end[1]
        return (dx * dx + dy * dy) ** 0.5 >= self.config.min_line_length
