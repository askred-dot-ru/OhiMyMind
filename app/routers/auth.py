from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.deps import current_user
from app.models import User
from app.schemas import LoginIn, RegisterIn, RegisterOut, UserOut
from app.security import (
    COOKIE_NAME,
    SESSION_MAX_AGE,
    dump_session,
    hash_password,
    verify_password,
)

router = APIRouter()


def _set_session(response: Response, user: User) -> None:
    response.set_cookie(
        COOKIE_NAME,
        dump_session(str(user.id)),
        httponly=True,
        samesite="lax",
        secure=settings.cookie_secure,
        max_age=SESSION_MAX_AGE,
        path="/",
    )


@router.post("/auth/register", response_model=RegisterOut, status_code=201)
def register(payload: RegisterIn, db: Session = Depends(get_db)) -> RegisterOut:
    login = payload.login.strip()
    if not login:
        raise HTTPException(status_code=400, detail="login_required")
    exists = db.scalar(select(User.id).where(User.login == login))
    if exists:
        raise HTTPException(status_code=409, detail="login_taken")
    user = User(
        login=login,
        password_hash=hash_password(payload.password),
        role="user",
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return RegisterOut(id=user.id, login=user.login, role=user.role)


@router.post("/auth/login", response_model=UserOut)
def login(payload: LoginIn, response: Response, db: Session = Depends(get_db)) -> UserOut:
    user = db.scalar(select(User).where(User.login == payload.login.strip()))
    if user is None or not user.is_active or not verify_password(user.password_hash, payload.password):
        raise HTTPException(status_code=401, detail="invalid_credentials")
    _set_session(response, user)
    return UserOut(login=user.login, role=user.role)


@router.post("/auth/logout", status_code=204)
def logout(response: Response) -> Response:
    response.delete_cookie(COOKIE_NAME, path="/")
    return Response(status_code=204)


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(current_user)) -> UserOut:
    return UserOut(login=user.login, role=user.role)
