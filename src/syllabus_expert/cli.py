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
) -> None:
    """Extract MCQs from a PDF and print JSON."""
    paper = extract_mcqs(pdf, mode=mode)
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
    for warning in paper.warnings:
        typer.echo(f"warning: {warning}", err=True)


if __name__ == "__main__":
    app()
