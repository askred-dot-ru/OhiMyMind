import json

from cryptography.fernet import Fernet, InvalidToken

from app.config import settings


def _fernet() -> Fernet:
    key = settings.app_master_key.strip().encode("utf-8")
    return Fernet(key)


def encrypt_secret(payload: dict) -> bytes:
    raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    return _fernet().encrypt(raw)


def decrypt_secret(blob: bytes) -> dict:
    try:
        raw = _fernet().decrypt(blob)
    except InvalidToken as exc:
        raise ValueError("secret_decrypt_failed") from exc
    return json.loads(raw.decode("utf-8"))
