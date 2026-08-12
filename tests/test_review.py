import json
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from pathlib import Path
from threading import Thread

from syllabus_expert.db import get_paper, save_paper
from syllabus_expert.models import ExtractedPaper, MCQ, Option
from syllabus_expert.review.enrich import infer_subject, infer_topic
from syllabus_expert.review.server import make_handler
from tests.conftest import SAMPLE_TEXT
from tests.pdf_utils import write_pdf


def test_infer_subject_and_topic():
    assert infer_subject("1") == "Physics"
    assert infer_subject("90") == "Chemistry"
    assert infer_subject("100") == "Botany"
    assert infer_subject("180") == "Zoology"
    topic = infer_topic(
        "The ratio of their radii of gyration about an axis",
        "Physics",
    )
    assert topic == "Moment of Inertia, Radius of Gyration"


def _start(db: Path, uploads: Path) -> tuple[ThreadingHTTPServer, HTTPConnection]:
    server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(db, uploads))
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address
    return server, HTTPConnection(host, port, timeout=30)


def test_review_server_roundtrip(tmp_path: Path):
    db = tmp_path / "bank.db"
    uploads = tmp_path / "uploads"
    paper = ExtractedPaper(
        title="Practice Paper of NEET (UG) - 06",
        exam="NEET (UG)",
        source_path="paper.pdf",
        page_count=1,
        mcqs=[
            MCQ(
                number="1",
                question="The ratio of their radii of gyration is:",
                options=[
                    Option(letter="A", text="1 : 2"),
                    Option(letter="B", text="1 : √2"),
                ],
                answer="B",
                explanation="k = sqrt(I/M)",
            )
        ],
    )
    save_paper(db, paper)
    server, conn = _start(db, uploads)
    try:
        conn.request("GET", "/")
        home = conn.getresponse()
        assert home.status == 200
        html = home.read()
        assert b"Syllabus Expert" in html
        assert b"Upload PDFs" in html
        assert b"library.html" in html
        assert b"practice.html" in html
        assert b"--bg" in html
        assert b"#12151c" in html

        conn.request("GET", "/review")
        review = conn.getresponse()
        assert review.status == 200
        review_html = review.read()
        assert b"Review Assessment" in review_html
        assert b"katex" in review_html
        assert b"--bg" in review_html

        conn.request("GET", "/library")
        library = conn.getresponse()
        assert library.status == 200
        assert b"Library" in library.read()

        conn.request("GET", "/upload")
        upload = conn.getresponse()
        assert upload.status == 200
        assert b"Question paper PDF" in upload.read()

        conn.request("GET", "/practice")
        practice = conn.getresponse()
        assert practice.status == 200
        assert b"Start practice" in practice.read()

        conn.request("GET", "/css/site.css")
        css = conn.getresponse()
        assert css.status == 200
        assert b"--bg" in css.read()

        conn.request("GET", "/api/stats")
        stats = json.loads(conn.getresponse().read())
        assert stats["paper_count"] == 1
        assert stats["question_count"] == 1

        conn.request("GET", "/api/paper")
        payload = json.loads(conn.getresponse().read())
        assert payload["mcqs"][0]["subject"] == "Physics"
        assert payload["title"] == "Practice Paper of NEET (UG) - 06"
        assert payload["id"]

        payload["mcqs"][0]["answer"] = "A"
        body = json.dumps(payload).encode()
        conn.request(
            "PUT",
            "/api/paper",
            body=body,
            headers={"Content-Type": "application/json"},
        )
        assert conn.getresponse().status == 200
        saved = get_paper(db, payload["id"])
        assert saved is not None
        assert saved.mcqs[0].answer == "A"

        conn.request("DELETE", f"/api/paper?id={payload['id']}")
        deleted = json.loads(conn.getresponse().read())
        assert deleted["ok"] is True
        conn.request("GET", "/api/stats")
        empty_stats = json.loads(conn.getresponse().read())
        assert empty_stats["paper_count"] == 0
    finally:
        server.shutdown()
        server.server_close()


def test_ingest_upload_endpoint(tmp_path: Path):
    db = tmp_path / "bank.db"
    uploads = tmp_path / "uploads"
    paper_pdf = write_pdf(tmp_path / "paper.pdf", [SAMPLE_TEXT.strip()])
    key_pdf = write_pdf(
        tmp_path / "key.pdf",
        ["Q1.\nb\nNewton.\nQ2.\nc\nVector.\nQ3.\na\nUniform velocity.\n"],
    )
    server, conn = _start(db, uploads)
    try:
        boundary = "----CursorBoundary"
        chunks = []
        for name, path in (("paper", paper_pdf), ("answers", key_pdf)):
            data = path.read_bytes()
            chunks.append(
                (
                    f"--{boundary}\r\n"
                    f'Content-Disposition: form-data; name="{name}"; '
                    f'filename="{path.name}"\r\n'
                    "Content-Type: application/pdf\r\n\r\n"
                ).encode()
                + data
                + b"\r\n"
            )
        chunks.append(
            (
                f"--{boundary}\r\n"
                'Content-Disposition: form-data; name="exam"\r\n\r\n'
                "NEET (UG)\r\n"
            ).encode()
        )
        chunks.append(f"--{boundary}--\r\n".encode())
        body = b"".join(chunks)
        conn.request(
            "POST",
            "/api/ingest",
            body=body,
            headers={
                "Content-Type": f"multipart/form-data; boundary={boundary}",
                "Content-Length": str(len(body)),
            },
        )
        response = conn.getresponse()
        payload = json.loads(response.read())
        assert response.status == 200, payload
        assert len(payload["mcqs"]) == 3
        assert payload["mcqs"][0]["answer"] == "B"
        assert payload["id"]
    finally:
        server.shutdown()
        server.server_close()
