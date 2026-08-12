from __future__ import annotations

from pathlib import Path

import pytest

from syllabus_expert.pdf import PageText
from tests.pdf_utils import write_pdf


SAMPLE_TEXT = """
Physics — Practice Paper

1. The SI unit of force is
(a) Joule
(b) Newton
(c) Watt
(d) Pascal
Answer: b

2. Which of the following is a vector quantity?
A. Mass
B. Temperature
C. Velocity
D. Time
Ans. (C)

3. A body moving with uniform velocity has
(a) constant speed and constant direction
(b) constant speed but changing direction
(c) changing speed and constant direction
(d) changing speed and changing direction

Answer Key
1. b
2. c
3. a
"""


@pytest.fixture
def sample_text() -> str:
    return SAMPLE_TEXT.strip()


@pytest.fixture
def sample_pages(sample_text: str) -> list[PageText]:
    return [PageText(page=1, text=sample_text, char_count=len(sample_text))]


@pytest.fixture
def sample_pdf(tmp_path: Path, sample_text: str) -> Path:
    return write_pdf(tmp_path / "sample.pdf", [sample_text])
