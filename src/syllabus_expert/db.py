from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Iterator

from syllabus_expert.models import ExtractedPaper, MCQ, Option
from syllabus_expert.review.enrich import enrich_mcq

SCHEMA = """
CREATE TABLE IF NOT EXISTS papers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL DEFAULT 'Untitled assessment',
    exam TEXT,
    language TEXT NOT NULL DEFAULT 'English',
    difficulty TEXT NOT NULL DEFAULT 'medium',
    status TEXT NOT NULL DEFAULT 'draft',
    source_path TEXT,
    answer_key_path TEXT,
    page_count INTEGER NOT NULL DEFAULT 0,
    warnings TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS questions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    paper_id INTEGER NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
    number TEXT,
    question TEXT NOT NULL,
    answer TEXT,
    explanation TEXT,
    page INTEGER,
    source TEXT NOT NULL DEFAULT 'heuristic',
    subject TEXT,
    topic TEXT,
    difficulty TEXT,
    sort_order INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS options (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    question_id INTEGER NOT NULL REFERENCES questions(id) ON DELETE CASCADE,
    letter TEXT NOT NULL,
    text TEXT NOT NULL DEFAULT '',
    sort_order INTEGER NOT NULL DEFAULT 0
);
"""

_lock = Lock()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@contextmanager
def connect(db_path: Path) -> Iterator[sqlite3.Connection]:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with _lock:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.executescript(SCHEMA)
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()


def save_paper(db_path: Path, paper: ExtractedPaper) -> int:
    """Insert or replace a paper and its questions. Returns paper id."""
    for mcq in paper.mcqs:
        enrich_mcq(mcq)
    stamp = _now()
    with connect(db_path) as conn:
        if paper.id:
            conn.execute(
                """
                UPDATE papers SET title=?, exam=?, language=?, difficulty=?, status=?,
                    source_path=?, answer_key_path=?, page_count=?, warnings=?, updated_at=?
                WHERE id=?
                """,
                (
                    paper.title or "Untitled assessment",
                    paper.exam,
                    paper.language,
                    paper.difficulty,
                    paper.status,
                    paper.source_path,
                    paper.answer_key_path,
                    paper.page_count,
                    json.dumps(paper.warnings),
                    stamp,
                    paper.id,
                ),
            )
            conn.execute(
                "DELETE FROM options WHERE question_id IN (SELECT id FROM questions WHERE paper_id=?)",
                (paper.id,),
            )
            conn.execute("DELETE FROM questions WHERE paper_id=?", (paper.id,))
            paper_id = paper.id
        else:
            cur = conn.execute(
                """
                INSERT INTO papers (
                    title, exam, language, difficulty, status, source_path,
                    answer_key_path, page_count, warnings, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    paper.title or "Untitled assessment",
                    paper.exam,
                    paper.language,
                    paper.difficulty,
                    paper.status,
                    paper.source_path,
                    paper.answer_key_path,
                    paper.page_count,
                    json.dumps(paper.warnings),
                    stamp,
                    stamp,
                ),
            )
            paper_id = int(cur.lastrowid)
        _insert_questions(conn, paper_id, paper.mcqs)
    paper.id = paper_id
    return paper_id


def get_paper(db_path: Path, paper_id: int) -> ExtractedPaper | None:
    with connect(db_path) as conn:
        row = conn.execute("SELECT * FROM papers WHERE id=?", (paper_id,)).fetchone()
        if row is None:
            return None
        return _paper_from_row(conn, row)


def latest_paper_id(db_path: Path) -> int | None:
    with connect(db_path) as conn:
        row = conn.execute("SELECT id FROM papers ORDER BY id DESC LIMIT 1").fetchone()
        return int(row["id"]) if row else None


def list_papers(db_path: Path) -> list[dict[str, object]]:
    with connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT p.*, COUNT(q.id) AS question_count
            FROM papers p
            LEFT JOIN questions q ON q.paper_id = p.id
            GROUP BY p.id
            ORDER BY p.id DESC
            """
        ).fetchall()
        return [
            {
                "id": int(row["id"]),
                "title": row["title"],
                "exam": row["exam"],
                "status": row["status"],
                "question_count": int(row["question_count"]),
                "updated_at": row["updated_at"],
            }
            for row in rows
        ]


def _insert_questions(conn: sqlite3.Connection, paper_id: int, mcqs: list[MCQ]) -> None:
    for order, mcq in enumerate(mcqs):
        cur = conn.execute(
            """
            INSERT INTO questions (
                paper_id, number, question, answer, explanation, page, source,
                subject, topic, difficulty, sort_order
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                paper_id,
                mcq.number,
                mcq.question,
                mcq.answer,
                mcq.explanation,
                mcq.page,
                mcq.source,
                mcq.subject,
                mcq.topic,
                mcq.difficulty,
                order,
            ),
        )
        question_id = int(cur.lastrowid)
        for opt_order, option in enumerate(mcq.options):
            conn.execute(
                "INSERT INTO options (question_id, letter, text, sort_order) VALUES (?, ?, ?, ?)",
                (question_id, option.letter, option.text, opt_order),
            )


def _paper_from_row(conn: sqlite3.Connection, row: sqlite3.Row) -> ExtractedPaper:
    questions = conn.execute(
        "SELECT * FROM questions WHERE paper_id=? ORDER BY sort_order, id",
        (row["id"],),
    ).fetchall()
    mcqs: list[MCQ] = []
    for question in questions:
        options = conn.execute(
            "SELECT * FROM options WHERE question_id=? ORDER BY sort_order, id",
            (question["id"],),
        ).fetchall()
        mcqs.append(
            MCQ(
                number=question["number"],
                question=question["question"],
                options=[
                    Option(letter=option["letter"], text=option["text"]) for option in options
                ],
                answer=question["answer"],
                explanation=question["explanation"],
                page=question["page"],
                source=question["source"] or "heuristic",
                subject=question["subject"],
                topic=question["topic"],
                difficulty=question["difficulty"],
            )
        )
    warnings_raw = row["warnings"] or "[]"
    try:
        warnings = json.loads(warnings_raw)
    except json.JSONDecodeError:
        warnings = []
    return ExtractedPaper(
        id=int(row["id"]),
        source_path=row["source_path"] or "",
        answer_key_path=row["answer_key_path"],
        page_count=int(row["page_count"] or 0),
        title=row["title"],
        exam=row["exam"],
        language=row["language"] or "English",
        difficulty=row["difficulty"] or "medium",
        status=row["status"] or "draft",
        mcqs=mcqs,
        warnings=list(warnings),
    )
