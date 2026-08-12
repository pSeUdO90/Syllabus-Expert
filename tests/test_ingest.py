from pathlib import Path

from syllabus_expert.ingest import ingest_pdfs
from tests.conftest import SAMPLE_TEXT
from tests.pdf_utils import write_pdf


def test_ingest_pdfs_maps_answer_key(tmp_path: Path):
    paper_pdf = write_pdf(tmp_path / "paper.pdf", [SAMPLE_TEXT.strip()])
    key_pdf = write_pdf(
        tmp_path / "key.pdf",
        [
            """
Q1.
b
Newton is the SI unit of force.
Q2.
c
Velocity is a vector.
Q3.
a
Uniform velocity means constant speed and direction.
"""
        ],
    )
    db = tmp_path / "bank.db"
    uploads = tmp_path / "uploads"
    paper = ingest_pdfs(
        paper_pdf=paper_pdf,
        answer_pdf=key_pdf,
        db_path=db,
        uploads_dir=uploads,
        mode="heuristic",
        exam="NEET (UG)",
    )
    assert paper.id is not None
    assert len(paper.mcqs) == 3
    by_number = {mcq.number: mcq for mcq in paper.mcqs}
    assert by_number["1"].answer == "B"
    assert "Newton" in (by_number["1"].explanation or "")
    assert by_number["2"].answer == "C"
    assert by_number["3"].answer == "A"
    assert (uploads / Path(paper.source_path).name).exists()
