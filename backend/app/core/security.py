"""Customer session tokens.

Tokens are signed JWTs (HS256, JWT_SECRET) carrying only a subject id and a role:
no name, email or other personal data is put in a token.
"""

import uuid
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db

ROLE_USER = "user"


def _secret() -> str:
    if len(settings.jwt_secret) < 32:
        raise HTTPException(status_code=503, detail="Sessions are not configured: JWT_SECRET is missing or too short in .env")
    return settings.jwt_secret


def create_token(subject: str, role: str, ttl: timedelta) -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode({"sub": subject, "role": role, "iat": now, "exp": now + ttl}, _secret(), algorithm="HS256")


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, _secret(), algorithms=["HS256"], options={"require": ["sub", "role", "exp"]})
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Your session has expired. Please enter your details again.")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid session. Please enter your details again.")


def _bearer(authorization: str | None, missing: str = "Please enter your name and email to use the skin analysis.") -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail=missing)
    return authorization.split(" ", 1)[1].strip()


def current_user(authorization: str | None = Header(default=None), db: Session = Depends(get_db)):
    """The signed-up user making the request (401 if missing/invalid)."""
    from app.db.models import User

    claims = decode_token(_bearer(authorization))
    if claims.get("role") != ROLE_USER:
        raise HTTPException(status_code=403, detail="This action needs a user session.")
    try:
        user = db.get(User, uuid.UUID(claims["sub"]))
    except ValueError:
        user = None
    if not user:
        raise HTTPException(status_code=401, detail="Your details were not found. Please enter them again.")
    return user


def optional_user(authorization: str | None = Header(default=None), db: Session = Depends(get_db)):
    """The signed-up user when a session token is sent, else None (for endpoints open before signup)."""
    return current_user(authorization, db) if authorization else None


def client_ip(request: Request) -> str | None:
    """The requesting IP as seen by the server - never a value the browser sends in a body/header.
    Behind a reverse proxy, run uvicorn with --proxy-headers --forwarded-allow-ips=<proxy ip> so this
    is the real client address rather than the proxy's."""
    return request.client.host if request.client else None
