from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class Option(BaseModel):
    letter: str = Field(description="Option label such as A, B, C, or D.")
    text: str = Field(description="Option wording, without the leading letter.")


class MCQ(BaseModel):
    number: str | None = Field(
        default=None, description="Question number as printed, e.g. '12'."
    )
    question: str = Field(description="Full question stem, without options.")
    options: list[Option] = Field(default_factory=list)
    answer: str | None = Field(
        default=None, description="Correct option letter if present in the PDF."
    )
    explanation: str | None = None
    page: int | None = Field(
        default=None, description="1-indexed page where the question starts."
    )
    source: Literal["heuristic", "agent"] = "heuristic"
    subject: str | None = None
    topic: str | None = None
    difficulty: str | None = None


class ExtractedPaper(BaseModel):
    id: int | None = None
    source_path: str = ""
    answer_key_path: str | None = None
    page_count: int = 0
    title: str | None = None
    exam: str | None = None
    language: str = "English"
    difficulty: str = "medium"
    status: Literal["draft", "published"] = "draft"
    mcqs: list[MCQ] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    def to_json(self, *, indent: int = 2) -> str:
        return self.model_dump_json(indent=indent)

    def to_csv_rows(self) -> list[dict[str, str]]:
        rows: list[dict[str, str]] = []
        for mcq in self.mcqs:
            row = {
                "number": mcq.number or "",
                "question": mcq.question,
                "answer": mcq.answer or "",
                "explanation": mcq.explanation or "",
                "page": str(mcq.page or ""),
                "source": mcq.source,
            }
            for option in mcq.options:
                row[f"option_{option.letter.upper()}"] = option.text
            rows.append(row)
        return rows
