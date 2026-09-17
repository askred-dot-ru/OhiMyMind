from datetime import timedelta

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from app.config import settings

COOKIE_NAME = "ohimymind_session"
SESSION_MAX_AGE = int(timedelta(days=14).total_seconds())

_hasher = PasswordHasher()
_signer = URLSafeTimedSerializer(settings.session_secret, salt="ohimymind-session")
_oauth_signer = URLSafeTimedSerializer(settings.session_secret, salt="ohimymind-gmail-oauth")


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except VerifyMismatchError:
        return False


def dump_session(user_id: str) -> str:
    return _signer.dumps({"uid": user_id})


def load_session(token: str) -> str | None:
    try:
        data = _signer.loads(token, max_age=SESSION_MAX_AGE)
    except (BadSignature, SignatureExpired):
        return None
    uid = data.get("uid")
    return str(uid) if uid else None


def dump_oauth_state(user_id: str, redirect_uri: str) -> str:
    return _oauth_signer.dumps({"uid": user_id, "redirect_uri": redirect_uri})


def load_oauth_state(token: str) -> tuple[str | None, str | None]:
    try:
        data = _oauth_signer.loads(token, max_age=600)
    except (BadSignature, SignatureExpired):
        return None, None
    uid = data.get("uid")
    redirect = data.get("redirect_uri")
    return (str(uid) if uid else None), (str(redirect) if redirect else None)
