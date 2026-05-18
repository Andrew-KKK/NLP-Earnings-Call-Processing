"""Convert a .docx upload into newline-separated plain text."""

from __future__ import annotations

from pathlib import Path

from docx import Document


def docx_to_text(path: Path) -> str:
    if path.suffix.lower() != ".docx":
        raise ValueError(f"Expected .docx, got {path.suffix}")
    doc = Document(str(path))
    paragraphs = [p.text.strip() for p in doc.paragraphs if p.text and p.text.strip()]
    return "\n".join(paragraphs)
