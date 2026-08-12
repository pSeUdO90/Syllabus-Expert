from __future__ import annotations

import csv
import json
import sys
from pathlib import Path
from typing import Optional

import typer
from dotenv import load_dotenv

from syllabus_expert.models import ExtractedPaper
from syllabus_expert.pipeline import Mode, extract_mcqs

load_dotenv()

app = typer.Typer(
    add_completion=False,
    help="Extract multiple-choice questions from PDF exam papers.",
)


@app.command()
def extract(
    pdf: Path = typer.Argument(..., exists=True, readable=True, help="Input PDF."),
    output: Optional[Path] = typer.Option(
        None, "--output", "-o", help="Write JSON (or CSV if the path ends in .csv)."
    ),
    mode: Mode = typer.Option(
        "auto",
        "--mode",
        "-m",
        help="auto | heuristic | agent. agent needs OPENAI_API_KEY.",
    ),
    answers: Optional[Path] = typer.Option(
        None,
        "--answers",
        "-a",
        exists=True,
        readable=True,
        help="Answer-key PDF to map letters and explanations onto questions.",
    ),
) -> None:
    """Extract MCQs from a PDF and print JSON."""
    paper = extract_mcqs(pdf, mode=mode, answer_key=answers)
    _write(paper, output)
    _print_summary(paper)


@app.command("from-text")
def from_text(
    text_file: Path = typer.Argument(..., exists=True, readable=True),
    output: Optional[Path] = typer.Option(None, "--output", "-o"),
) -> None:
    """Parse already-extracted plain text (useful for debugging the heuristic)."""
    from syllabus_expert.heuristic import parse_mcqs
    from syllabus_expert.pdf import PageText

    text = text_file.read_text(encoding="utf-8")
    pages = [PageText(page=1, text=text, char_count=len(text))]
    mcqs, warnings = parse_mcqs(pages)
    paper = ExtractedPaper(
        source_path=str(text_file.resolve()),
        page_count=1,
        mcqs=mcqs,
        warnings=warnings,
    )
    _write(paper, output)
    _print_summary(paper)


@app.command()
def review(
    json_file: Optional[Path] = typer.Argument(
        None, help="Optional questions.json to import into the database."
    ),
    db: Path = typer.Option(
        Path("data/syllabus_expert.db"),
        "--db",
        help="SQLite database path.",
    ),
    host: str = typer.Option("127.0.0.1", "--host", help="Bind address."),
    port: int = typer.Option(8765, "--port", "-p", help="Port for the review UI."),
    open_browser: bool = typer.Option(
        True, "--open/--no-open", help="Open the UI in a browser."
    ),
) -> None:
    """Open the Review Assessment UI (database-backed)."""
    import webbrowser

    from syllabus_expert.db import save_paper
    from syllabus_expert.review.enrich import enrich_mcq
    from syllabus_expert.review.server import serve

    if json_file is not None:
        if not json_file.exists():
            raise typer.BadParameter(f"File not found: {json_file}")
        paper = ExtractedPaper.model_validate_json(json_file.read_text(encoding="utf-8"))
        for mcq in paper.mcqs:
            enrich_mcq(mcq)
        if not paper.title:
            paper.title = json_file.stem.replace("_", " ")
        if not paper.exam:
            paper.exam = "NEET (UG)"
        paper_id = save_paper(db, paper)
        typer.echo(f"Imported {len(paper.mcqs)} question(s) as paper #{paper_id} into {db}")

    url = f"http://{host}:{port}"
    typer.echo(f"Opening review UI at {url}")
    typer.echo(f"Database: {db.resolve()}")
    if open_browser:
        try:
            webbrowser.open(url)
        except Exception:
            pass
    serve(db, host=host, port=port)


def _write(paper: ExtractedPaper, output: Path | None) -> None:
    payload = paper.model_dump()
    if output is None:
        json.dump(payload, sys.stdout, indent=2, ensure_ascii=False)
        sys.stdout.write("\n")
        return

    output.parent.mkdir(parents=True, exist_ok=True)
    if output.suffix.lower() == ".csv":
        rows = paper.to_csv_rows()
        fieldnames: list[str] = []
        for row in rows:
            for key in row:
                if key not in fieldnames:
                    fieldnames.append(key)
        with output.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
    else:
        output.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")


def _print_summary(paper: ExtractedPaper) -> None:
    typer.echo(
        f"Extracted {len(paper.mcqs)} MCQ(s) from {paper.page_count} page(s).",
        err=True,
    )
    answered = sum(1 for mcq in paper.mcqs if mcq.answer)
    if answered:
        typer.echo(f"Mapped {answered} answer(s) from the answer key.", err=True)
    for warning in paper.warnings:
        typer.echo(f"warning: {warning}", err=True)


if __name__ == "__main__":
    app()
