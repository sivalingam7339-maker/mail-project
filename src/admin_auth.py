"""Short-lived signed bearer tokens for the local admin dashboard."""

import base64
import hashlib
import hmac
import json
import secrets
import time

from fastapi import Header, HTTPException

from src.portal_db import _read_local_env

TOKEN_TTL_SECONDS = 60 * 60
_revoked_tokens: set[str] = set()


def _settings() -> tuple[str, str]:
    values = _read_local_env()
    username, password = values.get("ADMIN_USERNAME"), values.get("ADMIN_PASSWORD")
    if not username or not password:
        raise RuntimeError("Local admin credentials are not configured.")
    return username, password


def authenticate(username: str, password: str) -> str | None:
    expected_user, expected_password = _settings()
    if not (secrets.compare_digest(username, expected_user) and secrets.compare_digest(password, expected_password)):
        return None
    # A nonce keeps a newly issued login token distinct from a token revoked in
    # the same second.
    payload = json.dumps({"sub": expected_user, "exp": int(time.time()) + TOKEN_TTL_SECONDS, "jti": secrets.token_urlsafe(12)}, separators=(",", ":")).encode()
    encoded = base64.urlsafe_b64encode(payload).rstrip(b"=")
    signature = hmac.new(expected_password.encode(), encoded, hashlib.sha256).digest()
    return encoded.decode() + "." + base64.urlsafe_b64encode(signature).rstrip(b"=").decode()


def require_admin(authorization: str | None = Header(default=None)) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Admin authentication is required")
    try:
        token = authorization[7:]
        if token in _revoked_tokens:
            raise ValueError
        encoded, supplied = token.split(".", 1)
        _, password = _settings()
        expected = base64.urlsafe_b64encode(hmac.new(password.encode(), encoded.encode(), hashlib.sha256).digest()).rstrip(b"=").decode()
        payload = json.loads(base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)))
        if not secrets.compare_digest(supplied, expected) or payload["exp"] < time.time():
            raise ValueError
        return payload["sub"]
    except Exception:
        raise HTTPException(status_code=401, detail="Admin authentication is required")


def revoke(authorization: str | None) -> None:
    if authorization and authorization.startswith("Bearer "):
        _revoked_tokens.add(authorization[7:])
