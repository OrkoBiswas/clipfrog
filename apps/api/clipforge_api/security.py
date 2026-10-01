import hashlib
import secrets
from datetime import timedelta
from typing import Annotated

from fastapi import Depends, HTTPException, Request
from redis import Redis
from sqlalchemy import select
from sqlalchemy.orm import Session

from clipforge_api.config import settings
from clipforge_api.db import get_db
from clipforge_api.models import AuthSession, User, now

Db = Annotated[Session, Depends(get_db)]


def digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def create_session(db: Session, user: User) -> str:
    token = secrets.token_urlsafe(48)
    db.add(
        AuthSession(
            user_id=user.id,
            token_hash=digest(token),
            expires_at=now() + timedelta(days=settings().session_days),
        )
    )
    return token


def current_user(request: Request, db: Db) -> User:
    token = request.cookies.get("clipforge_session", "")
    session = db.scalar(
        select(AuthSession).where(
            AuthSession.token_hash == digest(token), AuthSession.expires_at > now()
        )
    )
    if not session:
        raise HTTPException(401, "Please sign in to continue.")
    user = db.get(User, session.user_id)
    if not user:
        raise HTTPException(401, "Session expired.")
    return user


CurrentUser = Annotated[User, Depends(current_user)]


def rate_limit(request: Request) -> None:
    # Trust the socket peer, never a client-supplied forwarded header.
    address = request.client.host if request.client else "unknown"
    key = f"auth-rate:{address}"
    client = Redis.from_url(settings().redis_url)
    script = "local n=redis.call('INCR',KEYS[1]); if n==1 then redis.call('EXPIRE',KEYS[1],ARGV[1]) end; return n"
    if int(client.eval(script, 1, key, 60)) > 30:
        raise HTTPException(429, "Too many attempts. Try again in a minute.")
