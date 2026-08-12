from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from syllabus_expert.auth import hash_password, new_token, verify_password

ROLES = ("admin", "teacher", "student")
DEFAULT_ADMIN_USERNAME = "admin"
DEFAULT_ADMIN_PASSWORD = "admin"
SESSION_DAYS = 7

ORG_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'student',
    display_name TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sessions (
    token TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    expires_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS subjects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    sort_order INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS chapters (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    subject_id INTEGER NOT NULL REFERENCES subjects(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    sort_order INTEGER NOT NULL DEFAULT 0,
    UNIQUE(subject_id, name)
);

CREATE TABLE IF NOT EXISTS topics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chapter_id INTEGER NOT NULL REFERENCES chapters(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    sort_order INTEGER NOT NULL DEFAULT 0,
    UNIQUE(chapter_id, name)
);

CREATE TABLE IF NOT EXISTS tests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    created_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    subject TEXT,
    chapter TEXT,
    topic TEXT,
    question_count INTEGER NOT NULL DEFAULT 0,
    time_limit_minutes INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS test_questions (
    test_id INTEGER NOT NULL REFERENCES tests(id) ON DELETE CASCADE,
    question_id INTEGER NOT NULL REFERENCES questions(id) ON DELETE CASCADE,
    sort_order INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (test_id, question_id)
);
"""

DEFAULT_SUBJECTS = ("Physics", "Chemistry", "Botany", "Zoology")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _parse_ts(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def ensure_org(conn: sqlite3.Connection) -> None:
    conn.executescript(ORG_SCHEMA)
    cols = {row[1] for row in conn.execute("PRAGMA table_info(questions)")}
    if "chapter" not in cols:
        conn.execute("ALTER TABLE questions ADD COLUMN chapter TEXT")
    if conn.execute("SELECT COUNT(*) AS n FROM users").fetchone()["n"] == 0:
        conn.execute(
            "INSERT INTO users (username, password_hash, role, display_name, created_at) VALUES (?, ?, ?, ?, ?)",
            (
                DEFAULT_ADMIN_USERNAME,
                hash_password(DEFAULT_ADMIN_PASSWORD),
                "admin",
                "Administrator",
                _now(),
            ),
        )
    if conn.execute("SELECT COUNT(*) AS n FROM subjects").fetchone()["n"] == 0:
        for order, name in enumerate(DEFAULT_SUBJECTS):
            conn.execute(
                "INSERT INTO subjects (name, sort_order) VALUES (?, ?)",
                (name, order),
            )


def _user_row(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return {
        "id": int(row["id"]),
        "username": row["username"],
        "role": row["role"],
        "display_name": row["display_name"] or row["username"],
        "created_at": row["created_at"],
    }


def list_users(db_path: Path) -> list[dict[str, Any]]:
    from syllabus_expert.db import connect

    with connect(db_path) as conn:
        rows = conn.execute(
            "SELECT id, username, role, display_name, created_at FROM users ORDER BY id"
        ).fetchall()
        return [_user_row(row) for row in rows]  # type: ignore[misc]


def create_user(
    db_path: Path,
    *,
    username: str,
    password: str,
    role: str = "student",
    display_name: str | None = None,
) -> dict[str, Any]:
    from syllabus_expert.db import connect

    username = username.strip()
    role = role.strip().lower()
    if not username:
        raise ValueError("Username is required")
    if role not in ROLES:
        raise ValueError("Role must be admin, teacher, or student")
    if len(password) < 4:
        raise ValueError("Password must be at least 4 characters")
    with connect(db_path) as conn:
        try:
            cur = conn.execute(
                "INSERT INTO users (username, password_hash, role, display_name, created_at) VALUES (?, ?, ?, ?, ?)",
                (username, hash_password(password), role, display_name or username, _now()),
            )
        except sqlite3.IntegrityError as exc:
            raise ValueError("Username already exists") from exc
        row = conn.execute(
            "SELECT id, username, role, display_name, created_at FROM users WHERE id=?",
            (cur.lastrowid,),
        ).fetchone()
        return _user_row(row)  # type: ignore[return-value]


def delete_user(db_path: Path, user_id: int) -> bool:
    from syllabus_expert.db import connect

    with connect(db_path) as conn:
        row = conn.execute("SELECT role FROM users WHERE id=?", (user_id,)).fetchone()
        if row is None:
            return False
        if row["role"] == "admin":
            admins = conn.execute(
                "SELECT COUNT(*) AS n FROM users WHERE role='admin'"
            ).fetchone()["n"]
            if int(admins) <= 1:
                raise ValueError("Cannot delete the last admin")
        conn.execute("DELETE FROM sessions WHERE user_id=?", (user_id,))
        conn.execute("DELETE FROM users WHERE id=?", (user_id,))
        return True


def authenticate(db_path: Path, username: str, password: str) -> dict[str, Any] | None:
    from syllabus_expert.db import connect

    with connect(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE username=?", (username.strip(),)
        ).fetchone()
        if row is None or not verify_password(password, row["password_hash"]):
            return None
        return _user_row(row)


def create_session(db_path: Path, user_id: int) -> str:
    from syllabus_expert.db import connect

    token = new_token()
    expires = (datetime.now(timezone.utc) + timedelta(days=SESSION_DAYS)).isoformat(
        timespec="seconds"
    )
    with connect(db_path) as conn:
        conn.execute(
            "INSERT INTO sessions (token, user_id, expires_at) VALUES (?, ?, ?)",
            (token, user_id, expires),
        )
    return token


def user_for_session(db_path: Path, token: str | None) -> dict[str, Any] | None:
    from syllabus_expert.db import connect

    if not token:
        return None
    with connect(db_path) as conn:
        row = conn.execute(
            """
            SELECT u.id, u.username, u.role, u.display_name, u.created_at, s.expires_at
            FROM sessions s JOIN users u ON u.id = s.user_id
            WHERE s.token=?
            """,
            (token,),
        ).fetchone()
        if row is None:
            return None
        if _parse_ts(row["expires_at"]) < datetime.now(timezone.utc):
            conn.execute("DELETE FROM sessions WHERE token=?", (token,))
            return None
        return _user_row(row)


def delete_session(db_path: Path, token: str | None) -> None:
    from syllabus_expert.db import connect

    if not token:
        return
    with connect(db_path) as conn:
        conn.execute("DELETE FROM sessions WHERE token=?", (token,))


def _get_or_create_subject(conn: sqlite3.Connection, name: str) -> int:
    name = name.strip()
    row = conn.execute("SELECT id FROM subjects WHERE name=?", (name,)).fetchone()
    if row:
        return int(row["id"])
    cur = conn.execute(
        "INSERT INTO subjects (name, sort_order) VALUES (?, ?)",
        (name, 100),
    )
    return int(cur.lastrowid)


def _get_or_create_chapter(conn: sqlite3.Connection, subject_id: int, name: str) -> int:
    name = name.strip()
    row = conn.execute(
        "SELECT id FROM chapters WHERE subject_id=? AND name=?",
        (subject_id, name),
    ).fetchone()
    if row:
        return int(row["id"])
    cur = conn.execute(
        "INSERT INTO chapters (subject_id, name, sort_order) VALUES (?, ?, 0)",
        (subject_id, name),
    )
    return int(cur.lastrowid)


def _get_or_create_topic(conn: sqlite3.Connection, chapter_id: int, name: str) -> int:
    name = name.strip()
    row = conn.execute(
        "SELECT id FROM topics WHERE chapter_id=? AND name=?",
        (chapter_id, name),
    ).fetchone()
    if row:
        return int(row["id"])
    cur = conn.execute(
        "INSERT INTO topics (chapter_id, name, sort_order) VALUES (?, ?, 0)",
        (chapter_id, name),
    )
    return int(cur.lastrowid)


def sync_taxonomy_from_questions(conn: sqlite3.Connection) -> None:
    rows = conn.execute(
        """
        SELECT DISTINCT TRIM(subject) AS subject, TRIM(chapter) AS chapter, TRIM(topic) AS topic
        FROM questions
        WHERE subject IS NOT NULL AND TRIM(subject) != ''
        """
    ).fetchall()
    for row in rows:
        subject_id = _get_or_create_subject(conn, row["subject"])
        chapter_name = row["chapter"] or row["subject"]
        chapter_id = _get_or_create_chapter(conn, subject_id, chapter_name)
        if row["topic"]:
            _get_or_create_topic(conn, chapter_id, row["topic"])


def list_taxonomy(db_path: Path) -> list[dict[str, Any]]:
    from syllabus_expert.db import connect

    with connect(db_path) as conn:
        subjects = conn.execute(
            "SELECT * FROM subjects ORDER BY sort_order, name"
        ).fetchall()
        result = []
        for subject in subjects:
            chapters = conn.execute(
                "SELECT * FROM chapters WHERE subject_id=? ORDER BY sort_order, name",
                (subject["id"],),
            ).fetchall()
            chapter_payload = []
            for chapter in chapters:
                topics = conn.execute(
                    "SELECT * FROM topics WHERE chapter_id=? ORDER BY sort_order, name",
                    (chapter["id"],),
                ).fetchall()
                chapter_payload.append(
                    {
                        "id": int(chapter["id"]),
                        "name": chapter["name"],
                        "topics": [
                            {"id": int(topic["id"]), "name": topic["name"]} for topic in topics
                        ],
                    }
                )
            result.append(
                {
                    "id": int(subject["id"]),
                    "name": subject["name"],
                    "chapters": chapter_payload,
                }
            )
        return result


def add_subject(db_path: Path, name: str) -> dict[str, Any]:
    from syllabus_expert.db import connect

    name = name.strip()
    if not name:
        raise ValueError("Subject name is required")
    with connect(db_path) as conn:
        try:
            cur = conn.execute(
                "INSERT INTO subjects (name, sort_order) VALUES (?, 50)", (name,)
            )
        except sqlite3.IntegrityError as exc:
            raise ValueError("Subject already exists") from exc
        return {"id": int(cur.lastrowid), "name": name, "chapters": []}


def add_chapter(db_path: Path, subject_id: int, name: str) -> dict[str, Any]:
    from syllabus_expert.db import connect

    name = name.strip()
    if not name:
        raise ValueError("Chapter name is required")
    with connect(db_path) as conn:
        parent = conn.execute("SELECT id FROM subjects WHERE id=?", (subject_id,)).fetchone()
        if parent is None:
            raise ValueError("Subject not found")
        try:
            cur = conn.execute(
                "INSERT INTO chapters (subject_id, name, sort_order) VALUES (?, ?, 0)",
                (subject_id, name),
            )
        except sqlite3.IntegrityError as exc:
            raise ValueError("Chapter already exists") from exc
        return {"id": int(cur.lastrowid), "name": name, "topics": []}


def add_topic(db_path: Path, chapter_id: int, name: str) -> dict[str, Any]:
    from syllabus_expert.db import connect

    name = name.strip()
    if not name:
        raise ValueError("Topic name is required")
    with connect(db_path) as conn:
        parent = conn.execute("SELECT id FROM chapters WHERE id=?", (chapter_id,)).fetchone()
        if parent is None:
            raise ValueError("Chapter not found")
        try:
            cur = conn.execute(
                "INSERT INTO topics (chapter_id, name, sort_order) VALUES (?, ?, 0)",
                (chapter_id, name),
            )
        except sqlite3.IntegrityError as exc:
            raise ValueError("Topic already exists") from exc
        return {"id": int(cur.lastrowid), "name": name}


def delete_subject(db_path: Path, subject_id: int) -> bool:
    from syllabus_expert.db import connect

    with connect(db_path) as conn:
        chapters = conn.execute(
            "SELECT id FROM chapters WHERE subject_id=?", (subject_id,)
        ).fetchall()
        for chapter in chapters:
            conn.execute("DELETE FROM topics WHERE chapter_id=?", (chapter["id"],))
        conn.execute("DELETE FROM chapters WHERE subject_id=?", (subject_id,))
        cur = conn.execute("DELETE FROM subjects WHERE id=?", (subject_id,))
        return cur.rowcount > 0


def delete_chapter(db_path: Path, chapter_id: int) -> bool:
    from syllabus_expert.db import connect

    with connect(db_path) as conn:
        conn.execute("DELETE FROM topics WHERE chapter_id=?", (chapter_id,))
        cur = conn.execute("DELETE FROM chapters WHERE id=?", (chapter_id,))
        return cur.rowcount > 0


def delete_topic(db_path: Path, topic_id: int) -> bool:
    from syllabus_expert.db import connect

    with connect(db_path) as conn:
        cur = conn.execute("DELETE FROM topics WHERE id=?", (topic_id,))
        return cur.rowcount > 0


def _mcq_from_question(conn: sqlite3.Connection, question: sqlite3.Row) -> dict[str, Any]:
    options = conn.execute(
        "SELECT letter, text FROM options WHERE question_id=? ORDER BY sort_order, id",
        (question["id"],),
    ).fetchall()
    return {
        "id": int(question["id"]),
        "number": question["number"],
        "question": question["question"],
        "options": [{"letter": opt["letter"], "text": opt["text"]} for opt in options],
        "answer": question["answer"],
        "explanation": question["explanation"],
        "subject": question["subject"],
        "chapter": question["chapter"],
        "topic": question["topic"],
        "difficulty": question["difficulty"],
        "paper_id": int(question["paper_id"]),
    }


def sample_questions(
    db_path: Path,
    *,
    subject: str | None = None,
    chapter: str | None = None,
    topic: str | None = None,
    paper_id: int | None = None,
    limit: int = 10,
) -> list[dict[str, Any]]:
    from syllabus_expert.db import connect

    limit = max(1, min(int(limit), 200))
    clauses = ["1=1"]
    params: list[Any] = []
    if paper_id:
        clauses.append("paper_id=?")
        params.append(paper_id)
    if subject:
        clauses.append("subject=?")
        params.append(subject)
    if chapter:
        clauses.append("chapter=?")
        params.append(chapter)
    if topic:
        clauses.append("topic=?")
        params.append(topic)
    sql = f"SELECT * FROM questions WHERE {' AND '.join(clauses)} ORDER BY RANDOM() LIMIT ?"
    params.append(limit)
    with connect(db_path) as conn:
        rows = conn.execute(sql, params).fetchall()
        return [_mcq_from_question(conn, row) for row in rows]


def create_test(
    db_path: Path,
    *,
    title: str,
    created_by: int | None,
    subject: str | None = None,
    chapter: str | None = None,
    topic: str | None = None,
    question_count: int = 10,
    time_limit_minutes: int = 0,
) -> dict[str, Any]:
    from syllabus_expert.db import connect

    title = (title or "").strip() or "Untitled test"
    questions = sample_questions(
        db_path,
        subject=subject or None,
        chapter=chapter or None,
        topic=topic or None,
        limit=question_count,
    )
    if not questions:
        raise ValueError("No questions match those filters")
    with connect(db_path) as conn:
        cur = conn.execute(
            """
            INSERT INTO tests (
                title, created_by, subject, chapter, topic, question_count,
                time_limit_minutes, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                title,
                created_by,
                subject or None,
                chapter or None,
                topic or None,
                len(questions),
                max(0, int(time_limit_minutes)),
                _now(),
            ),
        )
        test_id = int(cur.lastrowid)
        for order, question in enumerate(questions):
            conn.execute(
                "INSERT INTO test_questions (test_id, question_id, sort_order) VALUES (?, ?, ?)",
                (test_id, question["id"], order),
            )
    return get_test(db_path, test_id)  # type: ignore[return-value]


def list_tests(db_path: Path) -> list[dict[str, Any]]:
    from syllabus_expert.db import connect

    with connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT t.*, u.username AS created_by_name
            FROM tests t LEFT JOIN users u ON u.id = t.created_by
            ORDER BY t.id DESC
            """
        ).fetchall()
        return [
            {
                "id": int(row["id"]),
                "title": row["title"],
                "subject": row["subject"],
                "chapter": row["chapter"],
                "topic": row["topic"],
                "question_count": int(row["question_count"]),
                "time_limit_minutes": int(row["time_limit_minutes"]),
                "created_by": row["created_by_name"],
                "created_at": row["created_at"],
            }
            for row in rows
        ]


def get_test(db_path: Path, test_id: int) -> dict[str, Any] | None:
    from syllabus_expert.db import connect

    with connect(db_path) as conn:
        row = conn.execute("SELECT * FROM tests WHERE id=?", (test_id,)).fetchone()
        if row is None:
            return None
        links = conn.execute(
            """
            SELECT q.* FROM test_questions tq
            JOIN questions q ON q.id = tq.question_id
            WHERE tq.test_id=? ORDER BY tq.sort_order, q.id
            """,
            (test_id,),
        ).fetchall()
        return {
            "id": int(row["id"]),
            "title": row["title"],
            "subject": row["subject"],
            "chapter": row["chapter"],
            "topic": row["topic"],
            "question_count": int(row["question_count"]),
            "time_limit_minutes": int(row["time_limit_minutes"]),
            "created_at": row["created_at"],
            "questions": [_mcq_from_question(conn, question) for question in links],
        }


def delete_test(db_path: Path, test_id: int) -> bool:
    from syllabus_expert.db import connect

    with connect(db_path) as conn:
        conn.execute("DELETE FROM test_questions WHERE test_id=?", (test_id,))
        cur = conn.execute("DELETE FROM tests WHERE id=?", (test_id,))
        return cur.rowcount > 0


def start_practice(
    db_path: Path,
    *,
    test_id: int | None = None,
    subject: str | None = None,
    chapter: str | None = None,
    topic: str | None = None,
    paper_id: int | None = None,
    count: int = 10,
    time_limit_minutes: int = 0,
) -> dict[str, Any]:
    if test_id:
        test = get_test(db_path, test_id)
        if test is None:
            raise ValueError("Test not found")
        return test
    questions = sample_questions(
        db_path,
        subject=subject or None,
        chapter=chapter or None,
        topic=topic or None,
        paper_id=paper_id,
        limit=count,
    )
    if not questions:
        raise ValueError("No questions match those filters")
    return {
        "id": None,
        "title": "Custom practice",
        "subject": subject,
        "chapter": chapter,
        "topic": topic,
        "question_count": len(questions),
        "time_limit_minutes": max(0, int(time_limit_minutes or 0)),
        "questions": questions,
    }
