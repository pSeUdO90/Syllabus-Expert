from syllabus_expert.pdf import extract_pages, join_pages, render_page_png
from syllabus_expert.pipeline import extract_mcqs


def test_extract_pages_from_sample_pdf(sample_pdf):
    pages = extract_pages(sample_pdf)
    assert len(pages) == 1
    assert "SI unit of force" in pages[0].text
    joined = join_pages(pages)
    assert "<<<PAGE 1>>>" in joined


def test_render_page_png(sample_pdf):
    png = render_page_png(sample_pdf, 1)
    assert png[:8] == b"\x89PNG\r\n\x1a\n"


def test_pipeline_heuristic_from_pdf(sample_pdf):
    paper = extract_mcqs(sample_pdf, mode="heuristic")
    assert paper.page_count == 1
    assert len(paper.mcqs) == 3
    by_number = {mcq.number: mcq for mcq in paper.mcqs}
    assert by_number["1"].answer == "B"
    assert by_number["2"].answer == "C"
    assert by_number["3"].answer == "A"
    assert by_number["1"].source == "heuristic"


def test_pipeline_auto_without_api_key_stays_heuristic(sample_pdf, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    paper = extract_mcqs(sample_pdf, mode="auto")
    assert len(paper.mcqs) == 3
    assert all(mcq.source == "heuristic" for mcq in paper.mcqs)
