from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import User
from app.security import hash_password
from app.logging_setup import setup_logging
import logging

log = logging.getLogger("ohimymind.bootstrap")


def ensure_attachments_dir() -> None:
    Path(settings.attachments_dir).mkdir(parents=True, exist_ok=True)


def bootstrap_admin(db: Session) -> None:
    exists = db.scalar(select(User.id).where(User.role == "admin").limit(1))
    if exists:
        return
    login = settings.ohimymind_bootstrap_admin.strip()
    password = settings.ohimymind_bootstrap_password
    if not login or not password:
        raise RuntimeError("no admin user and OHIMYMIND_BOOTSTRAP_ADMIN/PASSWORD empty")
    user = User(login=login, password_hash=hash_password(password), role="admin", is_active=True)
    db.add(user)
    db.flush()
    log.info("bootstrap admin created login=%s", login)


def startup() -> None:
    setup_logging()
    from cryptography.fernet import Fernet

    Fernet(settings.app_master_key.strip().encode("utf-8"))
    if not settings.session_secret.strip():
        raise RuntimeError("SESSION_SECRET empty")
    ensure_attachments_dir()
