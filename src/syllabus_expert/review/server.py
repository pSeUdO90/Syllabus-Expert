from __future__ import annotations

import json
import mimetypes
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from syllabus_expert.db import (
    delete_paper,
    get_paper,
    latest_paper_id,
    list_papers,
    paper_stats,
    save_paper,
)
from syllabus_expert.ingest import ingest_pdfs, parse_multipart
from syllabus_expert.models import ExtractedPaper
from syllabus_expert.org import (
    add_chapter,
    add_subject,
    add_topic,
    authenticate,
    create_session,
    create_test,
    create_user,
    delete_chapter,
    delete_session,
    delete_subject,
    delete_test,
    delete_topic,
    delete_user,
    get_test,
    list_taxonomy,
    list_tests,
    list_users,
    start_practice,
    user_for_session,
)

STATIC_DIR = Path(__file__).parent / "static"
MAX_UPLOAD_BYTES = 60 * 1024 * 1024
mimetypes.add_type("text/css", ".css")
mimetypes.add_type("application/javascript", ".js")

PAGES = {
    "/": "index.html",
    "/index.html": "index.html",
    "/library": "library.html",
    "/library.html": "library.html",
    "/upload": "upload.html",
    "/upload.html": "upload.html",
    "/review": "review.html",
    "/review.html": "review.html",
    "/practice": "practice.html",
    "/practice.html": "practice.html",
    "/login": "login.html",
    "/login.html": "login.html",
    "/admin": "admin.html",
    "/admin.html": "admin.html",
}

PUBLIC_PAGES = {"/login", "/login.html"}
STAFF_ROLES = {"admin", "teacher"}

EXT_TYPES = {
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".html": "text/html; charset=utf-8",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".ico": "image/x-icon",
}


def render_html(name: str) -> bytes:
    """Serve pages with CSS/JS inlined so styles work behind path-prefix proxies."""
    html = (STATIC_DIR / name).read_text(encoding="utf-8")
    css = (STATIC_DIR / "css" / "site.css").read_text(encoding="utf-8")
    js = (STATIC_DIR / "js" / "site.js").read_text(encoding="utf-8")
    style = f"<style>\n{css}\n</style>"
    script = f"<script>\n{js}\n</script>"
    for href in ('href="css/site.css"', 'href="/css/site.css"'):
        html = html.replace(f'<link rel="stylesheet" {href} />', style)
    if "</body>" in html:
        html = html.replace("</body>", script + "\n</body>", 1)
    return html.encode("utf-8")


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

        def _session_token(self) -> str | None:
            auth = self.headers.get("Authorization", "")
            if auth.lower().startswith("bearer "):
                return auth.split(" ", 1)[1].strip() or None
            header = self.headers.get("X-Session-Token", "").strip()
            if header:
                return header
            raw = self.headers.get("Cookie", "")
            cookie = SimpleCookie()
            cookie.load(raw)
            morsel = cookie.get("se_session")
            return morsel.value if morsel else None

        def _user(self) -> dict | None:
            return user_for_session(db_path, self._session_token())

        def _read_json(self) -> dict:
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length) if length else b"{}"
            if not body:
                return {}
            payload = json.loads(body.decode("utf-8"))
            if not isinstance(payload, dict):
                raise ValueError("JSON object required")
            return payload

        def do_GET(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            path = parsed.path
            query = parse_qs(parsed.query)
            user = self._user()

            if path in PAGES:
                self._send_bytes(render_html(PAGES[path]), 200, "text/html; charset=utf-8")
                return
            if path.startswith("/api/"):
                if path == "/api/login":
                    self._send_json({"error": "Use POST to log in"}, status=405)
                    return
                if user is None:
                    self._send_json({"error": "Login required"}, status=401)
                    return
                self._api_get(path, query, user)
                return
            if self._try_static(path):
                return
            self._send_bytes(b"Not found", 404, "text/plain")

        def _api_get(self, path: str, query: dict[str, list[str]], user: dict) -> None:
            if path == "/api/me":
                self._send_json(user)
                return
            if path == "/api/stats":
                self._send_json(paper_stats(db_path))
                return
            if path == "/api/papers":
                self._send_json(list_papers(db_path))
                return
            if path == "/api/paper":
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
            if path == "/api/taxonomy":
                self._send_json(list_taxonomy(db_path))
                return
            if path == "/api/tests":
                raw_id = (query.get("id") or [None])[0]
                if raw_id:
                    test = get_test(db_path, int(raw_id))
                    if test is None:
                        self._send_json({"error": "Test not found"}, status=404)
                        return
                    self._send_json(test)
                    return
                self._send_json(list_tests(db_path))
                return
            if path == "/api/users":
                if user["role"] != "admin":
                    self._send_json({"error": "Admin only"}, status=403)
                    return
                self._send_json(list_users(db_path))
                return
            self._send_json({"error": "Not found"}, status=404)

        def do_PUT(self) -> None:  # noqa: N802
            user = self._user()
            if user is None:
                self._send_json({"error": "Login required"}, status=401)
                return
            if user["role"] not in STAFF_ROLES:
                self._send_json({"error": "Teacher or admin only"}, status=403)
                return
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

        def do_DELETE(self) -> None:  # noqa: N802
            user = self._user()
            if user is None:
                self._send_json({"error": "Login required"}, status=401)
                return
            parsed = urlparse(self.path)
            query = parse_qs(parsed.query)
            raw_id = (query.get("id") or [None])[0]
            if parsed.path == "/api/paper":
                if user["role"] not in STAFF_ROLES:
                    self._send_json({"error": "Teacher or admin only"}, status=403)
                    return
                if not raw_id:
                    self._send_json({"error": "Paper id is required"}, status=400)
                    return
                ok = delete_paper(db_path, int(raw_id))
                if not ok:
                    self._send_json({"error": "Paper not found"}, status=404)
                    return
                self._send_json({"ok": True, "id": int(raw_id)})
                return
            if parsed.path == "/api/users":
                if user["role"] != "admin":
                    self._send_json({"error": "Admin only"}, status=403)
                    return
                if not raw_id:
                    self._send_json({"error": "User id is required"}, status=400)
                    return
                try:
                    ok = delete_user(db_path, int(raw_id))
                except ValueError as exc:
                    self._send_json({"error": str(exc)}, status=400)
                    return
                if not ok:
                    self._send_json({"error": "User not found"}, status=404)
                    return
                self._send_json({"ok": True})
                return
            if parsed.path == "/api/subjects":
                if not self._staff(user):
                    return
                ok = delete_subject(db_path, int(raw_id or 0))
                self._send_json({"ok": ok}, status=200 if ok else 404)
                return
            if parsed.path == "/api/chapters":
                if not self._staff(user):
                    return
                ok = delete_chapter(db_path, int(raw_id or 0))
                self._send_json({"ok": ok}, status=200 if ok else 404)
                return
            if parsed.path == "/api/topics":
                if not self._staff(user):
                    return
                ok = delete_topic(db_path, int(raw_id or 0))
                self._send_json({"ok": ok}, status=200 if ok else 404)
                return
            if parsed.path == "/api/tests":
                if not self._staff(user):
                    return
                ok = delete_test(db_path, int(raw_id or 0))
                self._send_json({"ok": ok}, status=200 if ok else 404)
                return
            self._send_bytes(b"Not found", 404, "text/plain")

        def do_POST(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            path = parsed.path
            if path == "/api/login":
                try:
                    payload = self._read_json()
                except ValueError as exc:
                    self._send_json({"error": str(exc)}, status=400)
                    return
                user = authenticate(
                    db_path,
                    str(payload.get("username") or ""),
                    str(payload.get("password") or ""),
                )
                if user is None:
                    self._send_json({"error": "Invalid username or password"}, status=401)
                    return
                token = create_session(db_path, int(user["id"]))
                payload = dict(user)
                payload["token"] = token
                self._send_json(
                    payload,
                    headers={"Set-Cookie": f"se_session={token}; Path=/; HttpOnly; SameSite=Lax; Max-Age=604800"},
                )
                return
            user = self._user()
            if user is None:
                self._send_json({"error": "Login required"}, status=401)
                return
            if path == "/api/logout":
                delete_session(db_path, self._session_token())
                self._send_json(
                    {"ok": True},
                    headers={"Set-Cookie": "se_session=; Path=/; HttpOnly; Max-Age=0"},
                )
                return
            if path == "/api/practice/start":
                try:
                    payload = self._read_json()
                    result = start_practice(
                        db_path,
                        test_id=int(payload["test_id"]) if payload.get("test_id") else None,
                        subject=payload.get("subject") or None,
                        chapter=payload.get("chapter") or None,
                        topic=payload.get("topic") or None,
                        paper_id=int(payload["paper_id"]) if payload.get("paper_id") else None,
                        count=int(payload.get("count") or 10),
                        time_limit_minutes=int(payload.get("time_limit_minutes") or 0),
                    )
                except (ValueError, TypeError, KeyError) as exc:
                    self._send_json({"error": str(exc)}, status=400)
                    return
                self._send_json(result)
                return
            if path == "/api/users":
                if user["role"] != "admin":
                    self._send_json({"error": "Admin only"}, status=403)
                    return
                try:
                    payload = self._read_json()
                    created = create_user(
                        db_path,
                        username=str(payload.get("username") or ""),
                        password=str(payload.get("password") or ""),
                        role=str(payload.get("role") or "student"),
                        display_name=payload.get("display_name") or None,
                    )
                except ValueError as exc:
                    self._send_json({"error": str(exc)}, status=400)
                    return
                self._send_json(created, status=201)
                return
            if path == "/api/subjects":
                if not self._staff(user):
                    return
                try:
                    payload = self._read_json()
                    self._send_json(add_subject(db_path, str(payload.get("name") or "")), status=201)
                except ValueError as exc:
                    self._send_json({"error": str(exc)}, status=400)
                return
            if path == "/api/chapters":
                if not self._staff(user):
                    return
                try:
                    payload = self._read_json()
                    self._send_json(
                        add_chapter(
                            db_path,
                            int(payload.get("subject_id") or 0),
                            str(payload.get("name") or ""),
                        ),
                        status=201,
                    )
                except (ValueError, TypeError) as exc:
                    self._send_json({"error": str(exc)}, status=400)
                return
            if path == "/api/topics":
                if not self._staff(user):
                    return
                try:
                    payload = self._read_json()
                    self._send_json(
                        add_topic(
                            db_path,
                            int(payload.get("chapter_id") or 0),
                            str(payload.get("name") or ""),
                        ),
                        status=201,
                    )
                except (ValueError, TypeError) as exc:
                    self._send_json({"error": str(exc)}, status=400)
                return
            if path == "/api/tests":
                if not self._staff(user):
                    return
                try:
                    payload = self._read_json()
                    self._send_json(
                        create_test(
                            db_path,
                            title=str(payload.get("title") or ""),
                            created_by=int(user["id"]),
                            subject=payload.get("subject") or None,
                            chapter=payload.get("chapter") or None,
                            topic=payload.get("topic") or None,
                            question_count=int(payload.get("question_count") or 10),
                            time_limit_minutes=int(payload.get("time_limit_minutes") or 0),
                        ),
                        status=201,
                    )
                except (ValueError, TypeError) as exc:
                    self._send_json({"error": str(exc)}, status=400)
                return
            if path != "/api/ingest":
                self._send_bytes(b"Not found", 404, "text/plain")
                return
            if user["role"] not in STAFF_ROLES:
                self._send_json({"error": "Teacher or admin only"}, status=403)
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

        def _staff(self, user: dict) -> bool:
            if user["role"] in STAFF_ROLES:
                return True
            self._send_json({"error": "Teacher or admin only"}, status=403)
            return False

        def _try_static(self, url_path: str) -> bool:
            rel = url_path.lstrip("/")
            if not rel or ".." in rel.split("/"):
                return False
            path = (STATIC_DIR / rel).resolve()
            try:
                path.relative_to(STATIC_DIR.resolve())
            except ValueError:
                return False
            if not path.is_file():
                return False
            content_type = EXT_TYPES.get(path.suffix.lower())
            if content_type is None:
                guessed, _ = mimetypes.guess_type(path.name)
                content_type = guessed or "application/octet-stream"
                if content_type.startswith("text/") or content_type in {
                    "application/javascript",
                    "application/json",
                }:
                    content_type = f"{content_type}; charset=utf-8"
            self._send_file(path, content_type)
            return True

        def _send_file(self, path: Path, content_type: str) -> None:
            if not path.exists():
                self._send_bytes(b"Not found", 404, "text/plain")
                return
            self._send_bytes(path.read_bytes(), 200, content_type)

        def _redirect(self, location: str) -> None:
            self.send_response(302)
            self.send_header("Location", location)
            self.send_header("Content-Length", "0")
            self.end_headers()

        def _send_json(
            self,
            payload: object,
            status: int = 200,
            headers: dict[str, str] | None = None,
        ) -> None:
            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self._send_bytes(
                data, status, "application/json; charset=utf-8", extra=headers
            )

        def _send_bytes(
            self,
            data: bytes,
            status: int,
            content_type: str,
            extra: dict[str, str] | None = None,
        ) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            if extra:
                for key, value in extra.items():
                    self.send_header(key, value)
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
    print(f"Syllabus Expert: http://{host}:{port}")
    print(f"Database:        {db_path}")
    print("Default login:   admin / admin")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        server.server_close()
