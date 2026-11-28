"""Small standard-library HTTP application for the versioned LearnMate API."""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import mimetypes
import re
import time
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
from urllib.parse import parse_qs, unquote, urlparse

from . import __version__
from .config import ROOT, settings
from .db import db, migrate
from .seed import seed
from .services import auth, curiosity, learning
from .services.tutor import TutorService


API_PREFIX = "/api/v1"
STATIC = ROOT / "static"
_RATE_BUCKETS: Dict[str, list] = {}
_TUTOR = TutorService()


class APIError(Exception):
    def __init__(self, status: int, code: str, message: str):
        super().__init__(message)
        self.status, self.code, self.message = status, code, message


class Handler(BaseHTTPRequestHandler):
    server_version = "LearnMate/0.1"

    def log_message(self, fmt: str, *args: Any) -> None:
        # Keep local logs concise and avoid logging user message bodies.
        print("%s - %s" % (self.address_string(), fmt % args))

    def _rate_limit(self) -> None:
        now = time.time()
        address = self.client_address[0]
        bucket = [value for value in _RATE_BUCKETS.get(address, []) if now - value < 60]
        if len(bucket) >= settings.request_rate_per_minute:
            raise APIError(429, "rate_limited", "Too many requests. Please try again shortly.")
        bucket.append(now)
        _RATE_BUCKETS[address] = bucket

    def _json(self, status: int, payload: Dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "same-origin")
        self.send_header("X-Frame-Options", "DENY")
        self.end_headers()
        self.wfile.write(body)

    def _data(self, data: Any, status: int = 200, meta: Optional[Dict[str, Any]] = None) -> None:
        payload: Dict[str, Any] = {"data": data}
        if meta is not None:
            payload["meta"] = meta
        self._json(status, payload)

    def _body(self) -> Dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        if length > 1_000_000:
            raise APIError(413, "payload_too_large", "Request body cannot exceed 1 MB.")
        if length == 0:
            return {}
        try:
            value = json.loads(self.rfile.read(length).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise APIError(400, "invalid_json", "Request body must be valid JSON.") from exc
        if not isinstance(value, dict):
            raise APIError(400, "invalid_body", "Request body must be a JSON object.")
        return value

    def _user(self, roles: Tuple[str, ...] = ()) -> Dict[str, Any]:
        header = self.headers.get("Authorization", "")
        scheme, _, token = header.partition(" ")
        if scheme.lower() != "bearer" or not token:
            raise APIError(401, "unauthorized", "Sign in to continue.")
        try:
            user = auth.authenticate(token)
        except auth.AuthError as exc:
            raise APIError(exc.status, exc.code, exc.message) from exc
        if roles and user["role"] not in roles:
            raise APIError(403, "forbidden", "Your account does not have permission to access this resource.")
        return user

    def _dispatch(self, method: str) -> None:
        try:
            self._rate_limit()
            parsed = urlparse(self.path)
            path = unquote(parsed.path)
            if not path.startswith(API_PREFIX):
                if method == "GET":
                    self._static(path)
                    return
                raise APIError(404, "not_found", "This route does not exist.")
            query = parsed.query
            body = self._body() if method in ("POST", "PUT", "PATCH", "DELETE") else {}
            self._route(method, path, query, body)
        except APIError as exc:
            self._json(exc.status, {"error": {"code": exc.code, "message": exc.message}})
        except auth.AuthError as exc:
            self._json(exc.status, {"error": {"code": exc.code, "message": exc.message}})
        except PermissionError as exc:
            self._json(403, {"error": {"code": "forbidden", "message": str(exc)}})
        except LookupError as exc:
            self._json(404, {"error": {"code": "not_found", "message": str(exc)}})
        except ValueError as exc:
            self._json(400, {"error": {"code": "invalid_request", "message": str(exc)}})
        except Exception as exc:
            print("Unhandled API error: %s" % type(exc).__name__)
            self._json(500, {"error": {"code": "internal_error", "message": "Something went wrong. Please try again."}})

    def do_GET(self) -> None:
        self._dispatch("GET")

    def do_POST(self) -> None:
        self._dispatch("POST")

    def do_PATCH(self) -> None:
        self._dispatch("PATCH")

    def do_DELETE(self) -> None:
        self._dispatch("DELETE")

    def _static(self, path: str) -> None:
        if path in ("/", "/index.html"):
            target = ROOT / "index.html"
        elif path in ("/workspace", "/workspace/"):
            target = STATIC / "index.html"
        elif path == "/docs":
            target = STATIC / "docs.html"
        elif path == "/architecture":
            target = ROOT / "docs" / "architecture.md"
        elif path == "/assets" or path.startswith("/assets/"):
            target = (ROOT / path.lstrip("/")).resolve()
            if ROOT.joinpath("assets").resolve() not in target.parents:
                raise APIError(404, "not_found", "File not found.")
        else:
            target = (STATIC / path.lstrip("/")).resolve()
            if STATIC.resolve() not in target.parents:
                raise APIError(404, "not_found", "File not found.")
        if not target.is_file():
            raise APIError(404, "not_found", "File not found.")
        content = target.read_bytes()
        self.send_response(200)
        content_type = "text/markdown; charset=utf-8" if target.suffix == ".md" else (mimetypes.guess_type(str(target))[0] or "application/octet-stream")
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "same-origin")
        self.send_header("Content-Security-Policy", "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; script-src 'self' 'unsafe-inline'; connect-src 'self'; font-src 'self' data: https://fonts.gstatic.com")
        self.end_headers()
        self.wfile.write(content)

    def _route(self, method: str, path: str, query: str, body: Dict[str, Any]) -> None:
        if method == "GET" and path == API_PREFIX + "/health":
            self._data({"status": "ok", "version": __version__})
            return
        if method == "POST" and path == API_PREFIX + "/auth/register":
            try:
                self._data(auth.register(body), 201)
            except auth.AuthError:
                raise
            return
        if method == "POST" and path == API_PREFIX + "/auth/login":
            self._data(auth.login(str(body.get("email", "")), str(body.get("password", ""))))
            return
        if method == "POST" and path == API_PREFIX + "/auth/refresh":
            self._data(auth.refresh(str(body.get("refresh_token", ""))))
            return
        if method == "POST" and path == API_PREFIX + "/auth/logout":
            user = self._user()
            auth.logout(user)
            self._data({"signed_out": True})
            return
        if method == "GET" and path == API_PREFIX + "/auth/me":
            user = self._user()
            self._data(auth.public_user(user))
            return
        if method == "GET" and path == API_PREFIX + "/learners/me":
            user = self._user(("LEARNER",))
            self._data(learning.profile_for(user["id"]))
            return
        if path == API_PREFIX + "/learners/me" and method == "PATCH":
            user = self._user(("LEARNER",))
            self._data(learning.update_profile(user["id"], body))
            return
        if method == "GET" and path == API_PREFIX + "/analytics/overview":
            user = self._user(("LEARNER",))
            self._data(learning.overview(user))
            return
        if method == "GET" and path == API_PREFIX + "/courses":
            user = self._user()
            courses = learning.courses_for(user)
            self._data(courses, meta={"count": len(courses)})
            return
        match = re.fullmatch(re.escape(API_PREFIX) + r"/courses/([A-Za-z0-9-]+)/enroll", path)
        if method == "POST" and match:
            user = self._user(("LEARNER",))
            self._data(learning.enroll(user["id"], match.group(1)), 201)
            return
        match = re.fullmatch(re.escape(API_PREFIX) + r"/courses/([A-Za-z0-9-]+)/lessons", path)
        if method == "GET" and match:
            user = self._user(("LEARNER",))
            self._data(learning.lessons_for(match.group(1), user["id"]))
            return
        match = re.fullmatch(re.escape(API_PREFIX) + r"/lessons/([A-Za-z0-9-]+)/complete", path)
        if method == "POST" and match:
            user = self._user(("LEARNER",))
            self._data(learning.complete_lesson(user["id"], match.group(1)))
            return
        if path == API_PREFIX + "/goals":
            user = self._user(("LEARNER",))
            if method == "GET":
                self._data(learning.goals_for(user["id"]))
            elif method == "POST":
                self._data(learning.create_goal(user["id"], body), 201)
            else:
                raise APIError(405, "method_not_allowed", "This method is not supported for goals.")
            return
        match = re.fullmatch(re.escape(API_PREFIX) + r"/goals/([A-Za-z0-9-]+)", path)
        if method == "PATCH" and match:
            user = self._user(("LEARNER",))
            if not isinstance(body.get("completed"), bool):
                raise APIError(400, "invalid_request", "completed must be true or false.")
            self._data(learning.update_goal(user["id"], match.group(1), body["completed"]))
            return
        if method == "POST" and path == API_PREFIX + "/focus/sessions":
            user = self._user(("LEARNER",))
            self._data(learning.start_focus(user["id"], body), 201)
            return
        match = re.fullmatch(re.escape(API_PREFIX) + r"/focus/sessions/([A-Za-z0-9-]+)", path)
        if method == "PATCH" and match:
            user = self._user(("LEARNER",))
            self._data(learning.finish_focus(user["id"], match.group(1), str(body.get("state", "completed"))))
            return
        if method == "POST" and path == API_PREFIX + "/ai/tutor/messages":
            user = self._user(("LEARNER",))
            self._data(_TUTOR.reply(user, str(body.get("message", "")), body.get("conversation_id")), 201)
            return
        if method == "GET" and path == API_PREFIX + "/curiosity/articles":
            if self.headers.get("Authorization", "").lower().startswith("bearer "):
                user = self._user(("LEARNER",))
                self._data(curiosity.get_articles(user))
            else:
                self._data({"articles": curiosity.get_public_articles(), "recommendations_enabled": False, "recommended_topics": []})
            return
        if method == "GET" and path == API_PREFIX + "/curiosity/preferences":
            user = self._user(("LEARNER",))
            self._data(curiosity.preferences(user))
            return
        if method == "PATCH" and path == API_PREFIX + "/curiosity/preferences":
            user = self._user(("LEARNER",))
            if not isinstance(body.get("recommendations_enabled"), bool):
                raise APIError(400, "invalid_request", "recommendations_enabled must be true or false.")
            self._data(curiosity.preferences(user, body["recommendations_enabled"]))
            return
        if method == "POST" and path == API_PREFIX + "/curiosity/questions":
            user = self._user(("LEARNER",))
            self._data(curiosity.ask(user, body, _TUTOR), 201)
            return
        if method == "GET" and path == API_PREFIX + "/curiosity/questions":
            user = self._user(("LEARNER",))
            self._data(curiosity.history(user))
            return
        match = re.fullmatch(re.escape(API_PREFIX) + r"/curiosity/questions/([A-Za-z0-9-]+)/feedback", path)
        if method == "POST" and match:
            user = self._user(("LEARNER",))
            if not isinstance(body.get("helpful"), bool):
                raise APIError(400, "invalid_request", "helpful must be true or false.")
            self._data(curiosity.feedback(user, match.group(1), body["helpful"]))
            return
        match = re.fullmatch(re.escape(API_PREFIX) + r"/curiosity/articles/([A-Za-z0-9-]+)/events", path)
        if method == "POST" and match:
            user = self._user(("LEARNER",))
            self._data(curiosity.article_event(user, match.group(1), str(body.get("event", ""))), 201)
            return
        if method == "GET" and path == API_PREFIX + "/communities/rooms":
            if self.headers.get("Authorization", "").lower().startswith("bearer "):
                user = self._user(("LEARNER",))
                self._data(curiosity.rooms(user))
            else:
                self._data(curiosity.rooms())
            return
        match = re.fullmatch(re.escape(API_PREFIX) + r"/communities/rooms/([A-Za-z0-9-]+)/messages", path)
        if match:
            user = self._user(("LEARNER",))
            if method == "GET":
                try:
                    limit = int(parse_qs(query).get("limit", ["60"])[0])
                except ValueError as exc:
                    raise APIError(400, "invalid_request", "limit must be a number.") from exc
                self._data(curiosity.messages(user, match.group(1), limit))
            elif method == "POST":
                self._data(curiosity.post_message(user, match.group(1), str(body.get("body", ""))), 201)
            else:
                raise APIError(405, "method_not_allowed", "This method is not supported for room messages.")
            return
        match = re.fullmatch(re.escape(API_PREFIX) + r"/communities/messages/([A-Za-z0-9-]+)/report", path)
        if method == "POST" and match:
            user = self._user(("LEARNER",))
            self._data(curiosity.report_message(user, match.group(1), str(body.get("reason", ""))), 201)
            return
        raise APIError(404, "not_found", "This API route does not exist.")


def create_app() -> None:
    if settings.environment != "development" and settings.jwt_secret == "local-development-only-change-me":
        raise RuntimeError("Set JWT_SECRET before starting outside development.")
    migrate()
    seed()
    curiosity.seed_catalog()


def serve() -> None:
    create_app()
    server = ThreadingHTTPServer((settings.host, settings.port), Handler)
    print("LearnMate AI listening on http://%s:%s" % (settings.host, settings.port))
    print("API documentation: http://%s:%s/docs" % (settings.host, settings.port))
    server.serve_forever()
