from __future__ import annotations
from pypdf import PdfReader
from pathlib import Path


def load_pdf_text(path: str) -> str:
    reader = PdfReader(path)
    return "\n\n".join(page.extract_text() or "" for page in reader.pages)


def chunk(text: str, max_chars: int = 2000, overlap: int = 200):
    i = 0
    n = len(text)
    while i < n:
        yield text[i : i + max_chars]
        i += max(1, max_chars - overlap)
