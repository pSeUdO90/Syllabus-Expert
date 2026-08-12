from __future__ import annotations

import re
import uuid
from pathlib import Path

from syllabus_expert.db import save_paper
from syllabus_expert.models import ExtractedPaper
from syllabus_expert.pdf import extract_pages
from syllabus_expert.pipeline import Mode, extract_mcqs
from syllabus_expert.review.enrich import enrich_mcq


def infer_title(pdf_path: Path, fallback: str = "Untitled assessment") -> str:
    try:
        pages = extract_pages(pdf_path)
    except Exception:
        return fallback
    if not pages:
        return fallback
    for line in pages[0].text.splitlines():
        text = line.strip()
        if len(text) >= 8:
            return text[:160]
    return fallback


def ingest_pdfs(
    *,
    paper_pdf: Path,
    db_path: Path,
    uploads_dir: Path,
    answer_pdf: Path | None = None,
    mode: Mode = "heuristic",
    title: str | None = None,
    exam: str | None = None,
) -> ExtractedPaper:
    """Copy PDFs, extract MCQs, map the answer key, and store the paper."""
    uploads_dir.mkdir(parents=True, exist_ok=True)
    token = uuid.uuid4().hex[:8]
    stored_paper = uploads_dir / f"{token}_paper.pdf"
    stored_paper.write_bytes(Path(paper_pdf).read_bytes())
    stored_answers: Path | None = None
    if answer_pdf is not None:
        stored_answers = uploads_dir / f"{token}_answers.pdf"
        stored_answers.write_bytes(Path(answer_pdf).read_bytes())

    extracted = extract_mcqs(stored_paper, mode=mode, answer_key=stored_answers)
    for mcq in extracted.mcqs:
        enrich_mcq(mcq)
    extracted.title = (title or "").strip() or infer_title(stored_paper)
    extracted.exam = (exam or "").strip() or extracted.exam or "NEET (UG)"
    extracted.answer_key_path = str(stored_answers) if stored_answers else None
    extracted.source_path = str(stored_paper)
    save_paper(db_path, extracted)
    return extracted


def parse_multipart(
    content_type: str, body: bytes
) -> tuple[dict[str, str], dict[str, tuple[str, bytes]]]:
    """Parse a multipart/form-data body into fields and files."""
    match = re.search(r"boundary=([^;]+)", content_type, flags=re.I)
    if not match:
        raise ValueError("multipart boundary missing")
    boundary = match.group(1).strip().strip('"').encode("ascii")
    fields: dict[str, str] = {}
    files: dict[str, tuple[str, bytes]] = {}
    for raw_part in body.split(b"--" + boundary):
        part = raw_part.strip()
        if not part or part == b"--":
            continue
        header_blob, sep, content = part.partition(b"\r\n\r\n")
        if not sep:
            header_blob, sep, content = part.partition(b"\n\n")
        if content.endswith(b"\r\n"):
            content = content[:-2]
        elif content.endswith(b"\n"):
            content = content[:-1]
        headers = header_blob.decode("utf-8", "replace")
        name_match = re.search(r'name="([^"]+)"', headers)
        if not name_match:
            continue
        name = name_match.group(1)
        filename_match = re.search(r'filename="([^"]*)"', headers)
        if filename_match and filename_match.group(1):
            files[name] = (filename_match.group(1), content)
        else:
            fields[name] = content.decode("utf-8", "replace")
    return fields, files
