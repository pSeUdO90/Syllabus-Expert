from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from syllabus_expert.models import ExtractedPaper
from syllabus_expert.review.enrich import enrich_mcq

STATIC_DIR = Path(__file__).parent / "static"


def load_paper(path: Path) -> ExtractedPaper:
    raw = json.loads(path.read_text(encoding="utf-8"))
    paper = ExtractedPaper.model_validate(raw)
    if not paper.title:
        paper.title = "Practice Paper of NEET (UG) - 06"
    if not paper.exam:
        paper.exam = "NEET (UG)"
    for mcq in paper.mcqs:
        enrich_mcq(mcq)
    return paper


def make_handler(json_path: Path) -> type[BaseHTTPRequestHandler]:
    class ReviewHandler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: object) -> None:  # noqa: A003
            return

        def do_GET(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            if parsed.path in {"/", "/index.html"}:
                self._send_file(STATIC_DIR / "index.html", "text/html; charset=utf-8")
                return
            if parsed.path == "/api/paper":
                paper = load_paper(json_path)
                payload = paper.model_dump()
                self._send_json(payload)
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
            json_path.write_text(paper.model_dump_json(indent=2) + "\n", encoding="utf-8")
            self._send_json({"ok": True, "count": len(paper.mcqs)})

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


def serve(json_path: Path, *, host: str = "127.0.0.1", port: int = 8765) -> None:
    handler = make_handler(json_path.resolve())
    server = ThreadingHTTPServer((host, port), handler)
    print(f"Review UI: http://{host}:{port}")
    print(f"Questions: {json_path.resolve()}")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        server.server_close()
