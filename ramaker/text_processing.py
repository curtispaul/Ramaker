"""Utilities for cleaning and correcting OCR/text extraction output."""
from __future__ import annotations

import re
from typing import Iterable, List

from .pdf_processor import TextElement

COMMON_SUBSTITUTIONS = {
    "0": "O",
    "O": "0",
    "1": "I",
    "I": "1",
    "l": "1",
}

GRAVE_PATTERN = re.compile(r"\b([A-Z]{1,2}\d{1,4})\b")
LOT_PATTERN = re.compile(r"\b(LOT\s*\d+)\b", re.IGNORECASE)


def clean_text_value(value: str) -> str:
    text = value.strip()
    for source, target in COMMON_SUBSTITUTIONS.items():
        if source in text:
            text = text.replace(source, target)
    text = re.sub(r"\s+", " ", text)
    return text


def enrich_text_labels(texts: Iterable[TextElement]) -> List[TextElement]:
    cleaned: List[TextElement] = []
    for text in texts:
        value = clean_text_value(text.value)
        if GRAVE_PATTERN.search(value):
            value = value.upper()
        if LOT_PATTERN.search(value):
            value = value.upper().replace("LOT", "Lot")
        cleaned.append(
            TextElement(
                value=value,
                position=text.position,
                fontname=text.fontname,
                size=text.size,
            )
        )
    return cleaned
