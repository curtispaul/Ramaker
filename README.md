# Ramaker

Ramaker Codex with OpenAI

## Cemetery PDF to DXF Converter

This project provides a command-line interface (CLI) for converting cemetery map PDFs into DXF files. Vector linework is written to a `LINES` layer and text is written to a `TEXT` layer. Embedded PDF text is extracted directly when possible; optionally, Tesseract OCR can be used as a fallback for scanned maps.

### Requirements

* Python 3.10+
* System dependencies for PDF rasterisation/OCR (Ubuntu example):
  ```bash
  sudo apt-get update && sudo apt-get install -y \
      python3 python3-venv python3-pip \
      build-essential poppler-utils tesseract-ocr libtesseract-dev
  ```
* Python packages listed in `requirements.txt`:
  ```bash
  python -m venv .venv
  source .venv/bin/activate
  pip install -r requirements.txt
  ```

### Usage

Convert a cemetery PDF to DXF via the CLI:

```bash
python -m cemeteries.cli path/to/input.pdf path/to/output.dxf
```

Optional arguments:

* `--min-line-length` – minimum line length to retain (default `2.0`).
* `--ocr` – enable OCR fallback using Tesseract for scanned PDFs.

The CLI reports missing dependencies with actionable messages if a required library is not installed.

### Development

Run a quick syntax check:

```bash
python -m compileall cemeteries
```

Further enhancements could include curve approximation, better OCR post-processing, and configuration for scale/units.
