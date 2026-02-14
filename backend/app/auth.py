from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
from typing import Optional

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer


_bearer = HTTPBearer(auto_error=False)


def _b64url_encode(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode("utf-8").rstrip("=")


def _b64url_decode(s: str) -> bytes:
    pad = "=" * ((4 - (len(s) % 4)) % 4)
    return base64.urlsafe_b64decode((s + pad).encode("utf-8"))


def _sign(secret: str, msg: bytes) -> str:
    sig = hmac.new(secret.encode("utf-8"), msg, hashlib.sha256).digest()
    return _b64url_encode(sig)


def make_token(secret: str, subject: str, expires_in_seconds: int) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    now = int(time.time())
    payload = {"sub": subject, "iat": now, "exp": now + expires_in_seconds}

    h = _b64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    p = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    msg = f"{h}.{p}".encode("utf-8")
    s = _sign(secret, msg)
    return f"{h}.{p}.{s}"


def verify_token(secret: str, token: str) -> dict:
    parts = token.split(".")
    if len(parts) != 3:
        raise ValueError("invalid token format")
    h, p, s = parts
    msg = f"{h}.{p}".encode("utf-8")

    expected = _sign(secret, msg)
    if not hmac.compare_digest(expected, s):
        raise ValueError("invalid signature")

    payload = json.loads(_b64url_decode(p).decode("utf-8"))
    exp = int(payload.get("exp", 0))
    if int(time.time()) >= exp:
        raise ValueError("token expired")

    return payload


def get_admin_password() -> str:
    pw = os.getenv("ADMIN_PASSWORD", "")
    if not pw:
        raise RuntimeError("ADMIN_PASSWORD not set")
    return pw


def get_jwt_secret() -> str:
    secret = os.getenv("JWT_SECRET", "")
    if not secret:
        raise RuntimeError("JWT_SECRET not set")
    return secret


async def require_auth(
    request: Request,
    creds: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
) -> dict:
    if creds is None or creds.scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="Missing bearer token")

    try:
        payload = verify_token(get_jwt_secret(), creds.credentials)
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {e}")

    request.state.actor = payload.get("sub", "admin")
    return payload
