import json
from pathlib import Path

from syllabus_expert.db import save_paper
from syllabus_expert.models import ExtractedPaper, MCQ, Option
from tests.test_review import _login, _start


def test_login_and_admin_flow(tmp_path: Path):
    db = tmp_path / "bank.db"
    server, conn = _start(db, tmp_path / "uploads")
    try:
        conn.request("GET", "/login")
        login_page = conn.getresponse()
        assert login_page.status == 200
        assert b"Log in" in login_page.read()

        conn.request(
            "POST",
            "/api/login",
            body=json.dumps({"username": "admin", "password": "wrong"}).encode(),
            headers={"Content-Type": "application/json"},
        )
        bad = conn.getresponse()
        assert bad.status == 401
        bad.read()

        auth = _login(conn)
        conn.request("GET", "/api/me", headers=auth)
        me = json.loads(conn.getresponse().read())
        assert me["username"] == "admin"
        assert me["role"] == "admin"

        conn.request(
            "POST",
            "/api/login",
            body=json.dumps({"username": "admin", "password": "admin"}).encode(),
            headers={"Content-Type": "application/json"},
        )
        logged = conn.getresponse()
        session = json.loads(logged.read())
        assert logged.status == 200
        assert session["token"]
        conn.request(
            "GET",
            "/api/me",
            headers={"Authorization": "Bearer " + session["token"]},
        )
        via_header = json.loads(conn.getresponse().read())
        assert via_header["username"] == "admin"

        conn.request("GET", "/admin", headers=auth)
        admin_page = conn.getresponse()
        assert admin_page.status == 200
        assert b"Admin panel" in admin_page.read()

        conn.request(
            "POST",
            "/api/users",
            body=json.dumps(
                {
                    "username": "rita",
                    "password": "teach",
                    "role": "teacher",
                    "display_name": "Rita",
                }
            ).encode(),
            headers={"Content-Type": "application/json", **auth},
        )
        teacher = json.loads(conn.getresponse().read())
        assert teacher["role"] == "teacher"

        conn.request("GET", "/api/users", headers=auth)
        users = json.loads(conn.getresponse().read())
        assert {row["username"] for row in users} >= {"admin", "rita"}
    finally:
        server.shutdown()
        server.server_close()


def test_practice_from_bank_and_saved_test(tmp_path: Path):
    db = tmp_path / "bank.db"
    save_paper(
        db,
        ExtractedPaper(
            title="Bank",
            exam="NEET (UG)",
            mcqs=[
                MCQ(
                    number="1",
                    question="Force unit?",
                    options=[Option(letter="A", text="N"), Option(letter="B", text="J")],
                    answer="A",
                ),
                MCQ(
                    number="50",
                    question="pH of acid?",
                    options=[Option(letter="A", text="1"), Option(letter="B", text="14")],
                    answer="A",
                ),
            ],
        ),
    )
    server, conn = _start(db, tmp_path / "uploads")
    try:
        auth = _login(conn)
        conn.request("GET", "/api/taxonomy", headers=auth)
        tree = json.loads(conn.getresponse().read())
        names = {item["name"] for item in tree}
        assert "Physics" in names
        assert "Chemistry" in names

        conn.request(
            "POST",
            "/api/practice/start",
            body=json.dumps(
                {
                    "subject": "Physics",
                    "count": 1,
                    "time_limit_minutes": 5,
                }
            ).encode(),
            headers={"Content-Type": "application/json", **auth},
        )
        practice = json.loads(conn.getresponse().read())
        assert practice["question_count"] == 1
        assert practice["questions"][0]["subject"] == "Physics"
        assert practice["time_limit_minutes"] == 5

        conn.request(
            "POST",
            "/api/tests",
            body=json.dumps(
                {
                    "title": "Chem drill",
                    "subject": "Chemistry",
                    "question_count": 1,
                    "time_limit_minutes": 8,
                }
            ).encode(),
            headers={"Content-Type": "application/json", **auth},
        )
        created = conn.getresponse()
        test = json.loads(created.read())
        assert created.status == 201, test
        assert test["title"] == "Chem drill"
        assert len(test["questions"]) == 1

        conn.request(
            "POST",
            "/api/practice/start",
            body=json.dumps({"test_id": test["id"]}).encode(),
            headers={"Content-Type": "application/json", **auth},
        )
        taken = json.loads(conn.getresponse().read())
        assert taken["id"] == test["id"]
        assert taken["time_limit_minutes"] == 8
    finally:
        server.shutdown()
        server.server_close()
