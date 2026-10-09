from __future__ import annotations

import base64
import hashlib
import hmac

from fastapi import Cookie, Header, HTTPException, status

from .config import session_secret


COOKIE_NAME = "dorilab_session"


def issue_session(user_id: str) -> str:
    encoded = base64.urlsafe_b64encode(user_id.encode("utf-8")).decode("ascii").rstrip("=")
    signature = hmac.new(session_secret().encode(), encoded.encode(), hashlib.sha256).hexdigest()
    return f"{encoded}.{signature}"


def parse_session(value: str) -> str:
    try:
        encoded, signature = value.rsplit(".", 1)
        expected = hmac.new(session_secret().encode(), encoded.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected):
            raise ValueError("signature")
        padded = encoded + "=" * (-len(encoded) % 4)
        return base64.urlsafe_b64decode(padded).decode("utf-8")
    except (ValueError, UnicodeError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid session")


def actor(dorilab_session: str | None = Cookie(default=None, alias=COOKIE_NAME)) -> str:
    if not dorilab_session:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="session required")
    return parse_session(dorilab_session)


def csrf(x_dorilab_csrf: str | None = Header(default=None)) -> None:
    if x_dorilab_csrf != "1":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="CSRF header required")
