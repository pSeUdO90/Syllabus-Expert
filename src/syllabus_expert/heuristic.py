from __future__ import annotations

import re

from syllabus_expert.models import MCQ, Option
from syllabus_expert.pdf import PageText

# Q1. / Q.1 / Question 12:  — rest of the stem may be on later lines.
Q_START = re.compile(
    r"^\s*Q(?:uestion)?\.?\s*(\d+)\s*[.\:)]?\s*(.*)$",
    re.IGNORECASE,
)
# 1. / 1)  — used when the paper is not Q-numbered (and never inside Q-mode).
NUM_START = re.compile(r"^\s*(\d+)\s*[.\)\:]\s+(.*\S.*)$")
# A.  / A. text  / (a) text  / A) text
# Do not treat "(A) is true" as an option; that is assertion-reason wording.
OPTION_START = re.compile(
    r"^\s*(?:([A-D])\.|\(([A-Da-d])\)|([A-Da-d])\))\s*(.*)$",
)
ANSWER_LINE = re.compile(
    r"^\s*(?:Ans(?:wer)?s?|Correct(?:\s+answer)?)\s*[:.\-]\s*\(?([A-Da-d])\)?\s*\.?\s*$",
    re.IGNORECASE,
)
ANSWER_KEY_HEADING = re.compile(
    r"^\s*(?:answer\s*keys?|answers?)\s*[:.\-]?\s*$",
    re.IGNORECASE,
)
ANSWER_KEY_ITEM = re.compile(
    r"(\d+)\s*[\.\)\-:]\s*\(?([A-Da-d])\)?",
)
PAGE_MARKER = re.compile(r"^<<<PAGE (\d+)>>>\s*$")
SKIP_LINE = re.compile(
    r"""
    ^\s*(
        page\s+\d+
      | www\.
      | \d+\s*/\s*\d+
      | contact\s*:
      | section\s+\d+
      | part\s+[a-d]\b
      | marking\s+scheme\b
      | subjects\s*:
      | full\s+marks\s*:
      | total\s+questions\s*:
      | duration\s*:
      | practice\s+paper\b
    )
    """,
    re.IGNORECASE | re.VERBOSE,
)
INLINE_FOOTER = re.compile(
    r"\s*Page\s+\d+\s+of\s+\d+(?:\s*Contact:\s*\d+)?\s*",
    re.IGNORECASE,
)
LETTER_ONLY = re.compile(r"^\s*([A-Da-d])\s*$")


def parse_mcqs(pages: list[PageText]) -> tuple[list[MCQ], list[str]]:
    """Parse standard numbered MCQs from extracted PDF text."""
    warnings: list[str] = []
    lines: list[tuple[int, str]] = []
    for page in pages:
        lines.append((page.page, f"<<<PAGE {page.page}>>>"))
        for raw in page.text.splitlines():
            cleaned = INLINE_FOOTER.sub(" ", raw).strip()
            if cleaned:
                lines.append((page.page, cleaned))
            elif raw.strip():
                lines.append((page.page, raw.strip()))

    q_mode = any(Q_START.match(line) for _, line in lines)

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

        if PAGE_MARKER.match(stripped):
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

        q_match = Q_START.match(stripped)
        if q_match:
            flush()
            current = _Draft(
                number=q_match.group(1),
                question=q_match.group(2).strip(),
                page=page,
            )
            continue

        if not q_mode:
            num_match = NUM_START.match(stripped)
            if num_match:
                flush()
                current = _Draft(
                    number=num_match.group(1),
                    question=num_match.group(2).strip(),
                    page=page,
                )
                continue

        option_match = OPTION_START.match(stripped)
        if option_match and current is not None:
            letter = (
                option_match.group(1) or option_match.group(2) or option_match.group(3)
            ).upper()
            text = option_match.group(4).strip()
            if current.accepts_option(letter):
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

    def accepts_option(self, letter: str) -> bool:
        if not self.options:
            return letter == "A"
        last = self.options[-1].letter
        return len(letter) == 1 and ord(letter) == ord(last) + 1

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


def parse_answer_key(pages: list[PageText]) -> tuple[dict[str, tuple[str, str | None]], list[str]]:
    """Parse a NEET-style key: Q1. / c / explanation..."""
    warnings: list[str] = []
    mapping: dict[str, tuple[str, str | None]] = {}
    current_number: str | None = None
    current_letter: str | None = None
    explanation: list[str] = []

    def flush() -> None:
        nonlocal current_number, current_letter, explanation
        if current_number and current_letter:
            text = " ".join(" ".join(explanation).split()) or None
            mapping[current_number] = (current_letter, text)
        elif current_number:
            warnings.append(f"Answer key item Q{current_number} had no letter.")
        current_number = None
        current_letter = None
        explanation = []

    for page in pages:
        for raw in page.text.splitlines():
            stripped = INLINE_FOOTER.sub(" ", raw).strip()
            if not stripped or PAGE_MARKER.match(stripped) or SKIP_LINE.match(stripped):
                continue

            q_match = Q_START.match(stripped)
            if q_match:
                flush()
                current_number = q_match.group(1)
                rest = q_match.group(2).strip()
                if rest:
                    letter_match = LETTER_ONLY.match(rest)
                    if letter_match:
                        current_letter = letter_match.group(1).upper()
                    else:
                        explanation.append(rest)
                continue

            if current_number is None:
                continue

            if current_letter is None:
                letter_match = LETTER_ONLY.match(stripped)
                if letter_match:
                    current_letter = letter_match.group(1).upper()
                    continue

            explanation.append(stripped)

    flush()
    if not mapping:
        warnings.append("No Q-numbered answers found in the answer-key PDF.")
    return mapping, warnings


def apply_answer_key(
    mcqs: list[MCQ], mapping: dict[str, tuple[str, str | None]]
) -> list[str]:
    """Copy letters and explanations onto MCQs that share a question number."""
    warnings: list[str] = []
    used: set[str] = set()
    for mcq in mcqs:
        if not mcq.number or mcq.number not in mapping:
            continue
        letter, text = mapping[mcq.number]
        mcq.answer = letter
        if text:
            mcq.explanation = text
        used.add(mcq.number)

    missing = [mcq.number for mcq in mcqs if mcq.number and mcq.number not in mapping]
    extra = [number for number in mapping if number not in used]
    if missing:
        preview = ", ".join(f"Q{n}" for n in missing[:12])
        more = f" (+{len(missing) - 12} more)" if len(missing) > 12 else ""
        warnings.append(f"Answer key missing {len(missing)} question(s): {preview}{more}")
    if extra:
        warnings.append(
            f"Answer key has {len(extra)} item(s) with no matching question."
        )
    return warnings
