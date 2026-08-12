from __future__ import annotations

import re

from syllabus_expert.models import MCQ, Option
from syllabus_expert.pdf import PageText

QUESTION_START = re.compile(
    r"""
    ^\s*
    (?:
        Q(?:uestion)?\.?\s*(\d+)\s*[.\)\:]?   # Q.1 / Q1. / Question 1
      | (\d+)\s*[.\)\:]                         # 1. / 1) / 1:
    )
    \s+
    (.*\S.*)
    $
    """,
    re.IGNORECASE | re.VERBOSE,
)
OPTION_START = re.compile(
    r"^\s*(?:\(?([A-Da-d])\)|([A-Da-d])[\.\)])\s+(.*\S.*)$",
)
ANSWER_LINE = re.compile(
    r"^\s*(?:Ans(?:wer)?s?|Correct(?:\s+answer)?)\s*[:.\-]\s*\(?([A-Da-d])\)?\s*\.?\s*$",
    re.IGNORECASE,
)
ANSWER_KEY_HEADING = re.compile(
    r"^\s*(?:answer\s*keys?|answers?|key)\s*[:.\-]?\s*$",
    re.IGNORECASE,
)
ANSWER_KEY_ITEM = re.compile(
    r"(\d+)\s*[\.\)\-:]\s*\(?([A-Da-d])\)?",
)
PAGE_MARKER = re.compile(r"^<<<PAGE (\d+)>>>\s*$")
SKIP_LINE = re.compile(
    r"^\s*(page\s+\d+|www\.|\d+\s*/\s*\d+)\s*$",
    re.IGNORECASE,
)


def parse_mcqs(pages: list[PageText]) -> tuple[list[MCQ], list[str]]:
    """Parse standard numbered MCQs from extracted PDF text."""
    warnings: list[str] = []
    lines: list[tuple[int, str]] = []
    for page in pages:
        lines.append((page.page, f"<<<PAGE {page.page}>>>"))
        for raw in page.text.splitlines():
            lines.append((page.page, raw))

    questions: list[MCQ] = []
    answer_key: dict[str, str] = {}
    in_answer_key = False
    current: _Draft | None = None

    def flush() -> None:
        nonlocal current
        if current is None:
            return
        mcq = current.to_mcq()
        if mcq is not None:
            questions.append(mcq)
        elif current.question.strip():
            warnings.append(
                f"Skipped incomplete item near page {current.page}: "
                f"{current.question[:80]!r}"
            )
        current = None

    for page, line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        page_match = PAGE_MARKER.match(stripped)
        if page_match:
            continue

        if ANSWER_KEY_HEADING.match(stripped):
            flush()
            in_answer_key = True
            continue

        if in_answer_key:
            for number, letter in ANSWER_KEY_ITEM.findall(stripped):
                answer_key[number] = letter.upper()
            continue

        if SKIP_LINE.match(stripped):
            continue

        question_match = QUESTION_START.match(stripped)
        if question_match:
            flush()
            current = _Draft(
                number=question_match.group(1) or question_match.group(2),
                question=question_match.group(3).strip(),
                page=page,
            )
            continue

        option_match = OPTION_START.match(stripped)
        if option_match and current is not None:
            letter = (option_match.group(1) or option_match.group(2)).upper()
            text = option_match.group(3).strip()
            current.add_option(letter, text)
            continue

        answer_match = ANSWER_LINE.match(stripped)
        if answer_match and current is not None:
            current.answer = answer_match.group(1).upper()
            continue

        if current is not None:
            current.append_text(stripped)

    flush()

    if answer_key:
        for mcq in questions:
            if mcq.number and mcq.number in answer_key and not mcq.answer:
                mcq.answer = answer_key[mcq.number]

    if not questions:
        warnings.append(
            "No numbered MCQs matched the heuristic parser. "
            "Try --mode agent with an OpenAI-compatible API key."
        )

    return questions, warnings


class _Draft:
    def __init__(self, number: str, question: str, page: int) -> None:
        self.number = number
        self.question = question
        self.page = page
        self.options: list[Option] = []
        self.answer: str | None = None

    def add_option(self, letter: str, text: str) -> None:
        self.options.append(Option(letter=letter, text=text))

    def append_text(self, text: str) -> None:
        if self.options:
            last = self.options[-1]
            last.text = f"{last.text} {text}".strip()
        else:
            self.question = f"{self.question} {text}".strip()

    def to_mcq(self) -> MCQ | None:
        question = " ".join(self.question.split())
        options = [
            Option(letter=option.letter, text=" ".join(option.text.split()))
            for option in self.options
        ]
        if not question or len(options) < 2:
            return None
        return MCQ(
            number=self.number,
            question=question,
            options=options,
            answer=self.answer,
            page=self.page,
            source="heuristic",
        )
