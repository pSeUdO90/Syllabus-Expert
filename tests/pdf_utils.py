from __future__ import annotations

from pathlib import Path

import pymupdf


def write_pdf(path: Path, pages: list[str]) -> Path:
    document = pymupdf.open()
    for text in pages:
        page = document.new_page()
        page.insert_textbox(pymupdf.Rect(72, 72, 520, 770), text, fontsize=11, fontname="helv")
    document.save(path)
    document.close()
    return path
