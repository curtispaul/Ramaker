# Ramaker Cemetery Map Toolkit

This repository provides a command-line workflow for converting cemetery PDF maps into CAD-friendly DXF files. The pipeline inspects each page to determine whether vector geometry or raster imagery is present, extracts linework and labels, normalizes coordinates for cleaning, applies OCR fallbacks, and finally recreates the drawing using DXF entities.

## Features

- **PDF inspection** using [PyMuPDF](https://pymupdf.readthedocs.io/) with optional [pdfplumber](https://github.com/jsvine/pdfplumber) verification to detect vector geometry, fonts, and embedded text.
- **Line extraction** from vector instructions when available; otherwise the page is rasterized and processed with OpenCV's probabilistic Hough transform to recover linear features.
- **Text capture** via native PDF extraction or Tesseract OCR when text is not embedded, followed by regex and substitution rules that target common cemetery label patterns (grave IDs, lot identifiers).
- **Coordinate normalization** to a unit square for cleaning heuristics (minimum length, angle snapping, polyline chaining) before converting back to PDF units for DXF output.
- **DXF generation** with [ezdxf](https://ezdxf.readthedocs.io/) where linework is written to the `LINES` layer and cleaned text is written to the `TEXT` layer.
- **Debug overlays** (optional) for reviewing rasterized pages and extracted geometry/text during tuning.

## Installation

This project targets Python 3.11+. Install the toolkit and its dependencies into a virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install pymupdf pdfplumber opencv-python-headless numpy pillow pytesseract ezdxf
```

> **Note:** Tesseract OCR must also be installed on your system when OCR is required. Refer to the [Tesseract documentation](https://tesseract-ocr.github.io/tessdoc/Installation.html) for platform-specific packages.

## Usage

The CLI accepts an input PDF map and outputs a DXF file. Additional options allow you to tweak rasterization resolution, cleaning heuristics, and debug visualizations.

```bash
python -m ramaker.cli \
    /path/to/cemetery_map.pdf \
    output/map.dxf \
    --dpi 400 \
    --min-segment-length 8 \
    --snap-angle 45 \
    --join-tolerance 4 \
    --text-height 0.2 \
    --debug-overlay debug/page.png \
    --log-level DEBUG
```

### Option reference

- `--dpi`: Rasterization resolution (in DPI) for line detection and OCR when vector data is absent. Increase for high-resolution scans.
- `--min-segment-length`: Discards short segments (in PDF units) before cleaning to reduce noise.
- `--snap-angle`: Snaps extracted segment angles to the closest increment (degrees) to enforce orthogonal/diagonal geometry.
- `--join-tolerance`: Maximum separation (PDF units) when chaining segments into polylines.
- `--text-height`: Height assigned to DXF text entities.
- `--debug-overlay`: Base filename for optional raster overlay exports (one file per page).
- `--log-level`: Adjusts verbosity; `DEBUG` prints detected fonts and additional diagnostics useful during calibration.

## Workflow overview

1. **Inspect:** Each page is scanned for vector paths and text spans. If none are found, the page is rasterized and the pipeline falls back to image processing and OCR.
2. **Extract:** Line segments are harvested from vector instructions or derived using Canny + Hough transforms on raster data. Text is collected from embedded spans or OCR output.
3. **Normalize & clean:** Coordinates are normalized to a unit square, filtered by length, snapped to canonical angles, and merged into polylines using configurable tolerances.
4. **Enhance labels:** Clean-up heuristics normalize spacing and letter-digit substitutions to correct common OCR mistakes and emphasize grave/lot identifiers.
5. **Export:** Cleaned geometry is scaled back to PDF units and written to DXF layers so the drawing opens at the same orientation and relative scale inside CAD tools.

## Debugging & tuning

- Enable `--log-level DEBUG` to list fonts detected on each page and to verify whether the page was treated as vector or raster.
- Provide `--debug-overlay` to capture raster renders of each page for manual inspection of the line and text detection steps.
- Adjust `--min-segment-length`, `--join-tolerance`, and `--snap-angle` to better match the survey style of specific cemetery maps.

## Limitations & assumptions

- The workflow relies on optional dependencies (OpenCV, pdfplumber, Pillow, pytesseract). When unavailable, the pipeline logs warnings and skips the related steps.
- Real-world scale is inferred from PDF units; if precise geospatial scaling is required, post-processing inside CAD/GIS software may still be necessary.
- OCR accuracy depends on Tesseract configuration and the clarity of scanned imagery; additional domain-specific dictionaries can be integrated within `ramaker/text_processing.py` if needed.

## Development

Run the CLI module locally for quick checks:

```bash
python -m ramaker.cli sample.pdf output.dxf --log-level DEBUG
```

Contributions should follow the existing module layout (`ramaker/pdf_processor.py`, `ramaker/geometry.py`, etc.) and keep third-party imports wrapped in try/except blocks so that missing optional dependencies degrade gracefully.
