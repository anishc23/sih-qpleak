"""JWT issuing and verification."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import jwt
from jwt import ExpiredSignatureError, InvalidTokenError

from app.config import settings


class TokenError(Exception):
    pass


def create_access_token(*, user_uid: str, role: str, email: str) -> tuple[str, int]:
    """Returns (token, expires_in_seconds)."""
    ttl = timedelta(minutes=settings.access_token_ttl_minutes)
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_uid,
        "role": role,
        "email": email,
        "iat": int(now.timestamp()),
        "exp": int((now + ttl).timestamp()),
        "iss": "securelock",
    }
    token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    return token, int(ttl.total_seconds())


def decode_access_token(token: str) -> dict:
    try:
        return jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
            issuer="securelock",
        )
    except ExpiredSignatureError as exc:
        raise TokenError("Session expired. Please sign in again.") from exc
    except InvalidTokenError as exc:
        raise TokenError("Invalid authentication token.") from exc
