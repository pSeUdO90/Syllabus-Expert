"""Extract multiple-choice questions from PDF exam papers."""

from syllabus_expert.models import ExtractedPaper, MCQ, Option
from syllabus_expert.pipeline import extract_mcqs

__all__ = ["MCQ", "Option", "ExtractedPaper", "extract_mcqs"]
__version__ = "0.1.0"
