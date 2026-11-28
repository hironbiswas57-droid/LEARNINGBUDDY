"""Password and signed-token helpers using only the Python standard library."""

import base64
import hashlib
import hmac
import json
import secrets
import time
from typing import Any, Dict

from .config import settings


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _unb64(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def password_hash(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 240000)
    return "pbkdf2_sha256$240000${}${}".format(_b64(salt), _b64(digest))


def password_matches(password: str, encoded: str) -> bool:
    try:
        algorithm, iterations, salt, expected = encoded.split("$")
        if algorithm != "pbkdf2_sha256":
            return False
        actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), _unb64(salt), int(iterations))
        return hmac.compare_digest(actual, _unb64(expected))
    except (ValueError, TypeError):
        return False


def issue_token(payload: Dict[str, Any]) -> str:
    header = _b64(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode())
    body = _b64(json.dumps(payload, separators=(",", ":")).encode())
    message = (header + "." + body).encode("ascii")
    signature = hmac.new(settings.jwt_secret.encode(), message, hashlib.sha256).digest()
    return header + "." + body + "." + _b64(signature)


def read_token(token: str) -> Dict[str, Any]:
    try:
        header, body, signature = token.split(".")
        header_claims = json.loads(_unb64(header).decode("utf-8"))
        if header_claims.get("alg") != "HS256" or header_claims.get("typ") != "JWT":
            raise ValueError("Invalid token header")
        message = (header + "." + body).encode("ascii")
        expected = hmac.new(settings.jwt_secret.encode(), message, hashlib.sha256).digest()
        if not hmac.compare_digest(expected, _unb64(signature)):
            raise ValueError("Invalid token signature")
        claims = json.loads(_unb64(body).decode("utf-8"))
        if not isinstance(claims.get("exp"), int) or claims["exp"] <= int(time.time()):
            raise ValueError("Token has expired")
        if claims.get("iss") != "learnmate-ai":
            raise ValueError("Invalid token issuer")
        return claims
    except (ValueError, KeyError, json.JSONDecodeError) as exc:
        raise ValueError("Invalid or expired token") from exc
