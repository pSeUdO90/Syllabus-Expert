from __future__ import annotations

from pathlib import Path
from typing import Literal

from syllabus_expert.heuristic import parse_mcqs
from syllabus_expert.models import ExtractedPaper, MCQ
from syllabus_expert.pdf import extract_pages

Mode = Literal["auto", "heuristic", "agent"]


def extract_mcqs(pdf_path: str | Path, *, mode: Mode = "auto") -> ExtractedPaper:
    """Extract MCQs from a PDF.

    auto: heuristic parser, then the LLM agent if a key is set and results look thin.
    heuristic: regex/layout parser only (no network).
    agent: tool-using LLM that reads pages (requires OPENAI_API_KEY).
    """
    path = Path(pdf_path).resolve()
    pages = extract_pages(path)
    warnings: list[str] = []

    empty_pages = [page.page for page in pages if page.char_count < 40]
    if empty_pages:
        warnings.append(
            "Low-text pages (possible scans): "
            + ", ".join(str(n) for n in empty_pages)
            + ". Use --mode agent with a vision-capable model."
        )

    if mode == "heuristic":
        mcqs, parse_warnings = parse_mcqs(pages)
        return ExtractedPaper(
            source_path=str(path),
            page_count=len(pages),
            mcqs=mcqs,
            warnings=warnings + parse_warnings,
        )

    if mode == "agent":
        from syllabus_expert.agent import run_agent

        mcqs, agent_warnings = run_agent(path)
        return ExtractedPaper(
            source_path=str(path),
            page_count=len(pages),
            mcqs=_dedupe(mcqs),
            warnings=warnings + agent_warnings,
        )

    mcqs, parse_warnings = parse_mcqs(pages)
    warnings.extend(parse_warnings)
    needs_agent = _should_escalate(mcqs, pages)
    if needs_agent:
        try:
            from syllabus_expert.agent import AgentError, run_agent

            agent_mcqs, agent_warnings = run_agent(path)
            warnings.extend(agent_warnings)
            if agent_mcqs:
                mcqs = agent_mcqs
        except AgentError as exc:
            warnings.append(str(exc))

    return ExtractedPaper(
        source_path=str(path),
        page_count=len(pages),
        mcqs=_dedupe(mcqs),
        warnings=warnings,
    )


def _should_escalate(mcqs: list[MCQ], pages: list) -> bool:
    if not mcqs:
        return True
    text_chars = sum(page.char_count for page in pages)
    if text_chars > 800 and len(mcqs) < 2:
        return True
    return False


def _dedupe(mcqs: list[MCQ]) -> list[MCQ]:
    seen: set[tuple[str | None, str]] = set()
    unique: list[MCQ] = []
    for mcq in mcqs:
        key = (mcq.number, mcq.question.lower())
        if key in seen:
            continue
        seen.add(key)
        unique.append(mcq)
    return unique
