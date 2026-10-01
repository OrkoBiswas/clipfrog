import secrets
import smtplib
from datetime import timedelta
from email.message import EmailMessage

from argon2 import PasswordHasher
from argon2.exceptions import VerificationError
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, Response
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError

from clipforge_api.config import settings
from clipforge_api.models import AuthSession, AuthToken, User, now
from clipforge_api.schemas import Credentials, Register, UserOut
from clipforge_api.security import CurrentUser, Db, create_session, digest, rate_limit

router = APIRouter(prefix="/auth", tags=["Authentication"])
hasher = PasswordHasher()
dummy_hash = hasher.hash("constant-time-missing-user-password")


def session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        "clipforge_session",
        token,
        httponly=True,
        secure=settings().cookie_secure,
        samesite="lax",
        path="/",
        max_age=settings().session_days * 86400,
    )


def send_token(email: str, token: str, purpose: str) -> None:
    message = EmailMessage()
    message["From"] = settings().mail_from
    message["To"] = email
    message["Subject"] = "Verify your email" if purpose == "verify" else "Reset your password"
    path = "verify-email" if purpose == "verify" else "reset-password"
    message.set_content(
        f"Open {settings().app_url}/{path}?token={token}\nThis link expires in one hour."
    )
    with smtplib.SMTP(settings().smtp_host, settings().smtp_port, timeout=10) as smtp:
        smtp.send_message(message)


def issue_token(db: Db, user: User, purpose: str, tasks: BackgroundTasks) -> None:
    token = secrets.token_urlsafe(48)
    db.execute(delete(AuthToken).where(AuthToken.user_id == user.id, AuthToken.purpose == purpose))
    db.add(
        AuthToken(
            user_id=user.id,
            token_hash=digest(token),
            purpose=purpose,
            expires_at=now() + timedelta(hours=1),
        )
    )
    tasks.add_task(send_token, user.email, token, purpose)


@router.post(
    "/register", response_model=UserOut, status_code=201, dependencies=[Depends(rate_limit)]
)
def register(body: Register, response: Response, db: Db, tasks: BackgroundTasks) -> User:
    user = User(
        email=str(body.email).lower(),
        name=body.name.strip(),
        password_hash=hasher.hash(body.password),
    )
    db.add(user)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "An account with this email already exists.") from None
    session_cookie(response, create_session(db, user))
    issue_token(db, user, "verify", tasks)
    db.commit()
    return user


@router.post("/login", response_model=UserOut, dependencies=[Depends(rate_limit)])
def login(body: Credentials, response: Response, db: Db) -> User:
    user = db.scalar(select(User).where(User.email == str(body.email).lower()))
    try:
        hasher.verify(user.password_hash if user else dummy_hash, body.password)
    except VerificationError:
        raise HTTPException(401, "Email or password is incorrect.") from None
    if not user:
        raise HTTPException(401, "Email or password is incorrect.")
    session_cookie(response, create_session(db, user))
    db.commit()
    return user


@router.post("/logout", status_code=204)
def logout(request: Request, response: Response, db: Db) -> None:
    db.execute(
        delete(AuthSession).where(
            AuthSession.token_hash == digest(request.cookies.get("clipforge_session", ""))
        )
    )
    db.commit()
    response.delete_cookie("clipforge_session", path="/")


class EmailInput(BaseModel):
    email: EmailStr


@router.post("/forgot-password", dependencies=[Depends(rate_limit)])
def forgot(body: EmailInput, db: Db, tasks: BackgroundTasks) -> dict[str, str]:
    user = db.scalar(select(User).where(User.email == str(body.email).lower()))
    if user:
        issue_token(db, user, "reset", tasks)
        db.commit()
    return {"message": "If the account exists, a reset link has been sent."}


class TokenInput(BaseModel):
    token: str = Field(min_length=32, max_length=128)


class ResetInput(TokenInput):
    password: str = Field(min_length=12, max_length=128)


def consume_token(db: Db, value: str, purpose: str) -> User:
    token = db.scalar(
        select(AuthToken)
        .where(
            AuthToken.token_hash == digest(value),
            AuthToken.purpose == purpose,
            AuthToken.expires_at > now(),
        )
        .with_for_update()
    )
    if not token:
        raise HTTPException(400, "This link is invalid or expired.")
    user = db.get(User, token.user_id)
    assert user is not None
    db.delete(token)
    return user


@router.post("/reset-password")
def reset(body: ResetInput, db: Db) -> dict[str, str]:
    user = consume_token(db, body.token, "reset")
    user.password_hash = hasher.hash(body.password)
    db.execute(delete(AuthSession).where(AuthSession.user_id == user.id))
    db.commit()
    return {"message": "Password updated. Please sign in."}


@router.post("/verify-email")
def verify(body: TokenInput, db: Db) -> dict[str, str]:
    user = consume_token(db, body.token, "verify")
    user.email_verified = True
    db.commit()
    return {"message": "Email verified."}


@router.post("/verification-email", dependencies=[Depends(rate_limit)])
def resend(user: CurrentUser, db: Db, tasks: BackgroundTasks) -> dict[str, str]:
    if not user.email_verified:
        issue_token(db, user, "verify", tasks)
        db.commit()
    return {"message": "Verification email sent."}
