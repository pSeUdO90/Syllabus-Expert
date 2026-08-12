import json
from http.client import HTTPConnection
from threading import Thread

from syllabus_expert.review.enrich import infer_subject, infer_topic
from syllabus_expert.review.server import make_handler
from http.server import ThreadingHTTPServer


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


def test_review_server_roundtrip(tmp_path):
    path = tmp_path / "questions.json"
    path.write_text(
        json.dumps(
            {
                "source_path": "paper.pdf",
                "page_count": 1,
                "mcqs": [
                    {
                        "number": "1",
                        "question": "The ratio of their radii of gyration is:",
                        "options": [
                            {"letter": "A", "text": "1 : 2"},
                            {"letter": "B", "text": "1 : √2"},
                        ],
                        "answer": "B",
                        "explanation": "k = sqrt(I/M)",
                    }
                ],
            }
        )
    )
    server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(path))
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address
    try:
        conn = HTTPConnection(host, port, timeout=5)
        conn.request("GET", "/")
        home = conn.getresponse()
        assert home.status == 200
        assert b"Review Assessment" in home.read()

        conn.request("GET", "/api/paper")
        payload = json.loads(conn.getresponse().read())
        assert payload["mcqs"][0]["subject"] == "Physics"
        assert payload["title"] == "Practice Paper of NEET (UG) - 06"

        payload["mcqs"][0]["answer"] = "A"
        body = json.dumps(payload).encode()
        conn.request("PUT", "/api/paper", body=body, headers={"Content-Type": "application/json"})
        assert conn.getresponse().status == 200
        saved = json.loads(path.read_text())
        assert saved["mcqs"][0]["answer"] == "A"
    finally:
        server.shutdown()
        server.server_close()
