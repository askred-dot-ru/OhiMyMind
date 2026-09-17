from __future__ import annotations

import uuid

from fastapi import Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import User
from app.security import COOKIE_NAME, load_session


def current_user(request: Request, db: Session = Depends(get_db)) -> User:
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        raise HTTPException(status_code=401, detail="unauthorized")
    uid = load_session(token)
    if not uid:
        raise HTTPException(status_code=401, detail="unauthorized")
    user = db.get(User, uuid.UUID(uid))
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="unauthorized")
    return user


def owner_scope(
    user: User,
    as_user_id: uuid.UUID | None = Query(default=None),
) -> uuid.UUID | None:
    if user.role == "admin":
        return as_user_id
    if as_user_id is not None and as_user_id != user.id:
        raise HTTPException(status_code=403, detail="forbidden")
    return user.id
