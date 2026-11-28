"""Identity and revocable session operations."""

import hashlib
import re
import secrets
import time
import uuid
from typing import Any, Dict

from ..config import settings
from ..db import db
from ..security import issue_token, password_hash, password_matches, read_token


EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


class AuthError(Exception):
    def __init__(self, code: str, message: str, status: int = 400):
        super().__init__(message)
        self.code, self.message, self.status = code, message, status


def _session_tokens(user: Dict[str, Any], session_id: str) -> Dict[str, str]:
    now = int(time.time())
    common = {"sub": user["id"], "sid": session_id, "iss": "learnmate-ai", "iat": now}
    access = issue_token(dict(common, typ="access", role=user["role"], exp=now + settings.access_token_minutes * 60))
    refresh = issue_token(dict(common, typ="refresh", exp=now + settings.refresh_token_days * 86400, jti=secrets.token_urlsafe(12)))
    return {"access_token": access, "refresh_token": refresh, "token_type": "Bearer", "expires_in": settings.access_token_minutes * 60}


def _refresh_digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def register(data: Dict[str, Any]) -> Dict[str, Any]:
    email = str(data.get("email", "")).strip().lower()
    name = str(data.get("display_name", "")).strip()
    password = str(data.get("password", ""))
    age_bracket = str(data.get("age_bracket", "adult"))
    role = str(data.get("role", "LEARNER")).upper()
    if len(email) > 254 or not EMAIL_PATTERN.match(email):
        raise AuthError("invalid_email", "Enter a valid email address.")
    if not name or len(name) > 100:
        raise AuthError("invalid_name", "Display name is required and must be under 100 characters.")
    if len(password) < 10 or len(password) > 256:
        raise AuthError("weak_password", "Use a password between 10 and 256 characters.")
    if age_bracket not in ("teen", "adult"):
        raise AuthError("guardian_consent_required", "Accounts for children under 13 require a guardian consent workflow before registration.", 403)
    if role != "LEARNER":
        raise AuthError("role_assignment_restricted", "Public registration is currently limited to learner accounts. Other roles require an authorized provisioning workflow.", 403)
    user_id = str(uuid.uuid4())
    with db() as connection:
        if connection.execute("SELECT 1 FROM users WHERE email=?", (email,)).fetchone():
            raise AuthError("email_unavailable", "An account with that email already exists.", 409)
        connection.execute("INSERT INTO users(id,email,password_hash,display_name,role,age_bracket) VALUES(?,?,?,?,?,?)", (user_id, email, password_hash(password), name, role, age_bracket))
        if role == "LEARNER":
            connection.execute("INSERT INTO learner_profiles(user_id) VALUES(?)", (user_id,))
        connection.execute("INSERT INTO audit_logs(id,actor_id,action,resource_type,resource_id) VALUES(?,?,?,?,?)", (str(uuid.uuid4()), user_id, "account.registered", "user", user_id))
    return login(email, password)


def login(email: str, password: str) -> Dict[str, Any]:
    email = str(email).strip().lower()
    with db() as connection:
        row = connection.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        if not row or not password_matches(str(password), row["password_hash"]):
            raise AuthError("invalid_credentials", "Email or password is incorrect.", 401)
        if not row["is_active"]:
            raise AuthError("account_inactive", "This account is inactive. Contact your administrator.", 403)
        user = dict(row)
        session_id = str(uuid.uuid4())
        tokens = _session_tokens(user, session_id)
        refresh_claims = read_token(tokens["refresh_token"])
        connection.execute("INSERT INTO sessions(id,user_id,refresh_hash,expires_at) VALUES(?,?,?,?)", (session_id, user["id"], _refresh_digest(tokens["refresh_token"]), refresh_claims["exp"]))
        connection.execute("INSERT INTO audit_logs(id,actor_id,action,resource_type,resource_id) VALUES(?,?,?,?,?)", (str(uuid.uuid4()), user["id"], "auth.login", "session", session_id))
        return {"user": public_user(user), "tokens": tokens}


def public_user(user: Dict[str, Any]) -> Dict[str, Any]:
    return {key: user[key] for key in ("id", "email", "display_name", "role", "age_bracket", "preferred_language") if key in user}


def authenticate(token: str) -> Dict[str, Any]:
    try:
        claims = read_token(token)
    except ValueError as exc:
        raise AuthError("unauthorized", str(exc), 401) from exc
    if claims.get("typ") != "access":
        raise AuthError("unauthorized", "An access token is required.", 401)
    with db() as connection:
        session = connection.execute("SELECT s.id AS session_id,s.expires_at AS session_expires_at,s.revoked_at AS session_revoked_at,u.* FROM sessions s JOIN users u ON u.id=s.user_id WHERE s.id=? AND u.id=?", (claims.get("sid"), claims.get("sub"))).fetchone()
        if not session or session["session_revoked_at"] or session["session_expires_at"] <= int(time.time()) or not session["is_active"]:
            raise AuthError("session_expired", "Your session has expired. Please sign in again.", 401)
        return dict(session)


def refresh(refresh_token: str) -> Dict[str, Any]:
    try:
        claims = read_token(refresh_token)
    except ValueError as exc:
        raise AuthError("invalid_refresh_token", str(exc), 401) from exc
    if claims.get("typ") != "refresh":
        raise AuthError("invalid_refresh_token", "A refresh token is required.", 401)
    with db() as connection:
        row = connection.execute("SELECT s.id AS session_id,s.expires_at AS session_expires_at,s.revoked_at AS session_revoked_at,s.refresh_hash,u.id AS id,u.email,u.display_name,u.role,u.age_bracket,u.preferred_language,u.is_active FROM sessions s JOIN users u ON u.id=s.user_id WHERE s.id=? AND u.id=?", (claims.get("sid"), claims.get("sub"))).fetchone()
        if not row or row["session_revoked_at"] or row["session_expires_at"] <= int(time.time()) or not row["is_active"] or not secrets.compare_digest(row["refresh_hash"], _refresh_digest(refresh_token)):
            raise AuthError("invalid_refresh_token", "This refresh token is no longer valid.", 401)
        tokens = _session_tokens(dict(row), row["session_id"])
        new_claims = read_token(tokens["refresh_token"])
        connection.execute("UPDATE sessions SET refresh_hash=?,expires_at=? WHERE id=?", (_refresh_digest(tokens["refresh_token"]), new_claims["exp"], row["session_id"]))
        return {"user": public_user(dict(row)), "tokens": tokens}


def logout(user: Dict[str, Any]) -> None:
    with db() as connection:
        connection.execute("UPDATE sessions SET revoked_at=CURRENT_TIMESTAMP WHERE id=? AND user_id=?", (user["session_id"], user["id"]))
