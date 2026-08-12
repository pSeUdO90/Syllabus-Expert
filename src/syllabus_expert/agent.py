from __future__ import annotations

import json
import os
from collections.abc import Callable
from pathlib import Path
from typing import Any

from openai import OpenAI

from syllabus_expert.models import MCQ, Option
from syllabus_expert.pdf import extract_pages, join_pages, render_page_png

SYSTEM_PROMPT = """You extract multiple-choice questions from exam PDF text.

Rules:
- Walk through the document in order using the tools.
- Record every MCQ you find. Do not invent questions or options.
- Keep the original wording. Include the printed question number when present.
- Option letters must be A, B, C, D (or however many appear).
- If an answer key or 'Ans:' line is present, set answer to that letter.
- If a page has almost no text it is probably a scan; use read_page_image.
- Call finish when you have processed the whole document.
"""

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_page_count",
            "description": "Return how many pages the PDF has.",
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_pages",
            "description": "Read extracted text for an inclusive 1-indexed page range.",
            "parameters": {
                "type": "object",
                "properties": {
                    "start": {"type": "integer", "minimum": 1},
                    "end": {"type": "integer", "minimum": 1},
                },
                "required": ["start", "end"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_page_image",
            "description": "Render a scanned or layout-heavy page as a PNG for visual reading.",
            "parameters": {
                "type": "object",
                "properties": {"page": {"type": "integer", "minimum": 1}},
                "required": ["page"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "record_mcqs",
            "description": "Save one or more extracted MCQs. Call this as you go.",
            "parameters": {
                "type": "object",
                "properties": {
                    "mcqs": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "number": {"type": ["string", "null"]},
                                "question": {"type": "string"},
                                "options": {
                                    "type": "array",
                                    "items": {
                                        "type": "object",
                                        "properties": {
                                            "letter": {"type": "string"},
                                            "text": {"type": "string"},
                                        },
                                        "required": ["letter", "text"],
                                    },
                                },
                                "answer": {"type": ["string", "null"]},
                                "explanation": {"type": ["string", "null"]},
                                "page": {"type": ["integer", "null"]},
                            },
                            "required": ["question", "options"],
                        },
                    }
                },
                "required": ["mcqs"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_recorded",
            "description": "List MCQs recorded so far (number + first 80 chars of the stem).",
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "finish",
            "description": "End extraction after the full PDF has been processed.",
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        },
    },
]


class AgentError(RuntimeError):
    pass


def run_agent(
    pdf_path: str | Path,
    *,
    max_turns: int = 24,
    client: OpenAI | None = None,
    model: str | None = None,
) -> tuple[list[MCQ], list[str]]:
    """Tool-using agent that reads a PDF and records structured MCQs."""
    path = Path(pdf_path)
    pages = extract_pages(path)
    warnings: list[str] = []
    recorded: list[MCQ] = []
    finished = False

    def get_page_count() -> dict[str, Any]:
        return {"page_count": len(pages)}

    def read_pages(start: int, end: int) -> dict[str, Any]:
        if start > end:
            start, end = end, start
        start = max(1, start)
        end = min(len(pages), end)
        selected = [page for page in pages if start <= page.page <= end]
        return {"text": join_pages(selected), "start": start, "end": end}

    def read_page_image(page: int) -> dict[str, Any]:
        png = render_page_png(path, page)
        return {
            "page": page,
            "image_png_base64_chars": len(png),
            "note": "Image attached in the next user message for you to read.",
            "_png": png,
        }

    def record_mcqs(mcqs: list[dict[str, Any]]) -> dict[str, Any]:
        added = 0
        for raw in mcqs:
            try:
                options = [
                    Option(letter=str(item["letter"]).upper(), text=str(item["text"]).strip())
                    for item in raw.get("options", [])
                ]
                question = str(raw.get("question", "")).strip()
                if not question or len(options) < 2:
                    warnings.append(f"Rejected incomplete MCQ: {question[:80]!r}")
                    continue
                answer = raw.get("answer")
                recorded.append(
                    MCQ(
                        number=_optional_str(raw.get("number")),
                        question=question,
                        options=options,
                        answer=_optional_str(answer).upper() if answer else None,
                        explanation=_optional_str(raw.get("explanation")),
                        page=raw.get("page"),
                        source="agent",
                    )
                )
                added += 1
            except (KeyError, TypeError, ValueError) as exc:
                warnings.append(f"Rejected malformed MCQ: {exc}")
        return {"recorded": added, "total": len(recorded)}

    def list_recorded() -> dict[str, Any]:
        return {
            "count": len(recorded),
            "items": [
                {
                    "number": mcq.number,
                    "preview": mcq.question[:80],
                    "option_count": len(mcq.options),
                    "answer": mcq.answer,
                    "page": mcq.page,
                }
                for mcq in recorded
            ],
        }

    def finish() -> dict[str, Any]:
        nonlocal finished
        finished = True
        return {"ok": True, "total": len(recorded)}

    handlers: dict[str, Callable[..., dict[str, Any]]] = {
        "get_page_count": get_page_count,
        "read_pages": read_pages,
        "read_page_image": read_page_image,
        "record_mcqs": record_mcqs,
        "list_recorded": list_recorded,
        "finish": finish,
    }

    llm = client or _default_client()
    chosen_model = model or os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                f"Extract every MCQ from this PDF: {path.name}. "
                "Start by calling get_page_count, then read the pages."
            ),
        },
    ]

    for _ in range(max_turns):
        response = llm.chat.completions.create(
            model=chosen_model,
            messages=messages,
            tools=TOOLS,
            tool_choice="auto",
        )
        choice = response.choices[0]
        message = choice.message
        messages.append(message.model_dump(exclude_none=True))

        if not message.tool_calls:
            if not finished:
                warnings.append("Model stopped without calling finish().")
            break

        for tool_call in message.tool_calls:
            name = tool_call.function.name
            arguments = json.loads(tool_call.function.arguments or "{}")
            handler = handlers.get(name)
            if handler is None:
                result: dict[str, Any] = {"error": f"Unknown tool: {name}"}
                png: bytes | None = None
            else:
                result = handler(**arguments)
                png = result.pop("_png", None)
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps({k: v for k, v in result.items() if k != "_png"}),
                }
            )
            if png is not None:
                import base64

                messages.append(
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": f"PNG render of page {arguments.get('page')}.",
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": "data:image/png;base64,"
                                    + base64.b64encode(png).decode("ascii")
                                },
                            },
                        ],
                    }
                )

        if finished:
            break
    else:
        warnings.append(f"Reached max_turns={max_turns} before finish().")

    if not recorded:
        warnings.append("Agent recorded no MCQs.")

    return recorded, warnings


def _default_client() -> OpenAI:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise AgentError(
            "OPENAI_API_KEY is not set. Use --mode heuristic, or set the key "
            "for --mode agent."
        )
    kwargs: dict[str, Any] = {"api_key": api_key}
    base_url = os.environ.get("OPENAI_BASE_URL")
    if base_url:
        kwargs["base_url"] = base_url
    return OpenAI(**kwargs)


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
