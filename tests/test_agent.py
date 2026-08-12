from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any

from syllabus_expert.agent import run_agent
from tests.pdf_utils import write_pdf


class FakeMessage:
    def __init__(self, *, tool_calls: list[Any] | None = None, content: str | None = None) -> None:
        self.role = "assistant"
        self.tool_calls = tool_calls
        self.content = content

    def model_dump(self, exclude_none: bool = True) -> dict[str, Any]:
        payload = {"role": self.role, "content": self.content, "tool_calls": self.tool_calls}
        if exclude_none:
            return {key: value for key, value in payload.items() if value is not None}
        return payload


class FakeClient:
    def __init__(self, turns: list[FakeMessage]) -> None:
        self.chat = SimpleNamespace(completions=self)
        self._turns = list(turns)

    def create(self, **kwargs: Any) -> SimpleNamespace:
        message = self._turns.pop(0)
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])


def _tool(name: str, arguments: dict[str, Any], call_id: str) -> SimpleNamespace:
    return SimpleNamespace(
        id=call_id,
        function=SimpleNamespace(name=name, arguments=json.dumps(arguments)),
    )


def test_agent_records_mcqs_via_tools(tmp_path):
    pdf = write_pdf(
        tmp_path / "tiny.pdf",
        ["1. Capital of France?\n(a) London\n(b) Paris\n(c) Rome\n(d) Madrid\nAnswer: b"],
    )
    client = FakeClient(
        [
            FakeMessage(
                tool_calls=[_tool("get_page_count", {}, "c1")],
            ),
            FakeMessage(
                tool_calls=[_tool("read_pages", {"start": 1, "end": 1}, "c2")],
            ),
            FakeMessage(
                tool_calls=[
                    _tool(
                        "record_mcqs",
                        {
                            "mcqs": [
                                {
                                    "number": "1",
                                    "question": "Capital of France?",
                                    "options": [
                                        {"letter": "A", "text": "London"},
                                        {"letter": "B", "text": "Paris"},
                                        {"letter": "C", "text": "Rome"},
                                        {"letter": "D", "text": "Madrid"},
                                    ],
                                    "answer": "B",
                                    "page": 1,
                                }
                            ]
                        },
                        "c3",
                    )
                ]
            ),
            FakeMessage(tool_calls=[_tool("finish", {}, "c4")]),
        ]
    )

    mcqs, warnings = run_agent(pdf, client=client, model="fake")
    assert len(mcqs) == 1
    assert mcqs[0].question == "Capital of France?"
    assert mcqs[0].answer == "B"
    assert mcqs[0].source == "agent"
    assert not any("recorded no MCQs" in w for w in warnings)
