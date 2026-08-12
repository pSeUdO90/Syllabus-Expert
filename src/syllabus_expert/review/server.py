from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from syllabus_expert.db import get_paper, latest_paper_id, list_papers, save_paper
from syllabus_expert.ingest import ingest_pdfs, parse_multipart
from syllabus_expert.models import ExtractedPaper

STATIC_DIR = Path(__file__).parent / "static"
MAX_UPLOAD_BYTES = 60 * 1024 * 1024


def empty_paper() -> ExtractedPaper:
    return ExtractedPaper(
        title="Untitled assessment",
        exam="NEET (UG)",
        language="English",
        difficulty="medium",
        status="draft",
    )


def make_handler(db_path: Path, uploads_dir: Path) -> type[BaseHTTPRequestHandler]:
    class ReviewHandler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: object) -> None:  # noqa: A003
            return

        def do_GET(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            if parsed.path in {"/", "/index.html"}:
                self._send_file(STATIC_DIR / "index.html", "text/html; charset=utf-8")
                return
            if parsed.path == "/api/papers":
                self._send_json(list_papers(db_path))
                return
            if parsed.path == "/api/paper":
                query = parse_qs(parsed.query)
                raw_id = (query.get("id") or [None])[0]
                paper_id = int(raw_id) if raw_id else latest_paper_id(db_path)
                if paper_id is None:
                    self._send_json(empty_paper().model_dump())
                    return
                paper = get_paper(db_path, paper_id)
                if paper is None:
                    self._send_json({"error": "Paper not found"}, status=404)
                    return
                self._send_json(paper.model_dump())
                return
            self._send_bytes(b"Not found", 404, "text/plain")

        def do_PUT(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            if parsed.path != "/api/paper":
                self._send_bytes(b"Not found", 404, "text/plain")
                return
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length)
            paper = ExtractedPaper.model_validate_json(body)
            paper_id = save_paper(db_path, paper)
            saved = get_paper(db_path, paper_id)
            self._send_json({"ok": True, "id": paper_id, "count": len(saved.mcqs) if saved else 0})

        def do_POST(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            if parsed.path != "/api/ingest":
                self._send_bytes(b"Not found", 404, "text/plain")
                return
            length = int(self.headers.get("Content-Length", "0"))
            if length > MAX_UPLOAD_BYTES:
                self._send_json({"error": "Upload too large"}, status=413)
                return
            body = self.rfile.read(length)
            try:
                fields, files = parse_multipart(self.headers.get("Content-Type", ""), body)
            except ValueError as exc:
                self._send_json({"error": str(exc)}, status=400)
                return
            paper_file = files.get("paper") or files.get("question_pdf")
            if not paper_file:
                self._send_json({"error": "Question paper PDF is required."}, status=400)
                return
            filename, paper_bytes = paper_file
            if not filename.lower().endswith(".pdf") or not paper_bytes.startswith(b"%PDF"):
                self._send_json({"error": "Question paper must be a PDF."}, status=400)
                return
            tmp_dir = uploads_dir / "tmp"
            tmp_dir.mkdir(parents=True, exist_ok=True)
            tmp_paper = tmp_dir / filename
            tmp_paper.write_bytes(paper_bytes)
            tmp_answers = None
            answers_file = files.get("answers") or files.get("answer_pdf")
            if answers_file and answers_file[0]:
                ans_name, ans_bytes = answers_file
                if not ans_name.lower().endswith(".pdf") or not ans_bytes.startswith(b"%PDF"):
                    self._send_json({"error": "Answer key must be a PDF."}, status=400)
                    return
                tmp_answers = tmp_dir / f"answers_{ans_name}"
                tmp_answers.write_bytes(ans_bytes)
            try:
                paper = ingest_pdfs(
                    paper_pdf=tmp_paper,
                    answer_pdf=tmp_answers,
                    db_path=db_path,
                    uploads_dir=uploads_dir,
                    mode="heuristic",
                    title=fields.get("title") or None,
                    exam=fields.get("exam") or None,
                )
            except Exception as exc:  # noqa: BLE001
                self._send_json({"error": f"Extraction failed: {exc}"}, status=500)
                return
            self._send_json(paper.model_dump())

        def _send_file(self, path: Path, content_type: str) -> None:
            if not path.exists():
                self._send_bytes(b"Not found", 404, "text/plain")
                return
            self._send_bytes(path.read_bytes(), 200, content_type)

        def _send_json(self, payload: object, status: int = 200) -> None:
            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self._send_bytes(data, status, "application/json; charset=utf-8")

        def _send_bytes(self, data: bytes, status: int, content_type: str) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)

    return ReviewHandler


def serve(
    db_path: Path,
    *,
    uploads_dir: Path | None = None,
    host: str = "127.0.0.1",
    port: int = 8765,
) -> None:
    db_path = db_path.resolve()
    uploads = (uploads_dir or db_path.parent / "uploads").resolve()
    uploads.mkdir(parents=True, exist_ok=True)
    handler = make_handler(db_path, uploads)
    server = ThreadingHTTPServer((host, port), handler)
    print(f"Review UI: http://{host}:{port}")
    print(f"Database:  {db_path}")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        server.server_close()
