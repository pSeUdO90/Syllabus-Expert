import json
from pathlib import Path

from syllabus_expert.db import get_paper, list_papers, save_paper
from syllabus_expert.models import ExtractedPaper, MCQ, Option
from syllabus_expert.review.enrich import enrich_mcq


def test_save_and_load_paper(tmp_path: Path):
    db = tmp_path / "bank.db"
    paper = ExtractedPaper(
        title="NEET Practice",
        exam="NEET (UG)",
        source_path="paper.pdf",
        page_count=1,
        mcqs=[
            MCQ(
                number="1",
                question="The ratio of their radii of gyration is:",
                options=[
                    Option(letter="A", text="1 : 2"),
                    Option(letter="B", text="1 : √2"),
                ],
                answer="B",
                explanation="k = sqrt(I/M)",
            )
        ],
    )
    enrich_mcq(paper.mcqs[0])
    paper_id = save_paper(db, paper)
    loaded = get_paper(db, paper_id)
    assert loaded is not None
    assert loaded.title == "NEET Practice"
    assert len(loaded.mcqs) == 1
    assert loaded.mcqs[0].answer == "B"
    assert loaded.mcqs[0].subject == "Physics"
    assert loaded.mcqs[0].options[1].text == "1 : √2"

    loaded.mcqs[0].answer = "A"
    save_paper(db, loaded)
    again = get_paper(db, paper_id)
    assert again is not None
    assert again.mcqs[0].answer == "A"
    assert len(list_papers(db)) == 1
