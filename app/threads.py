from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import MailMessage, MailThread

_SUBJ_PREFIX = re.compile(
    r"^\s*((re|fw|fwd|aw|sv|отв|пересл)(\[\d+\])?[:：])\s*",
    re.IGNORECASE,
)


def normalize_message_id(value: str | None) -> str:
    if not value:
        return ""
    return value.strip().strip("<>").strip()


def normalize_subject(subject: str | None) -> str:
    text = (subject or "").strip()
    prev = None
    while prev != text:
        prev = text
        text = _SUBJ_PREFIX.sub("", text).strip()
    return text.casefold()


def participant_key(addresses: list[str]) -> str:
    cleaned = sorted({a.strip().casefold() for a in addresses if a and a.strip()})
    return ",".join(cleaned)


def split_references(header: str | None) -> list[str]:
    if not header:
        return []
    return [normalize_message_id(part) for part in header.replace(",", " ").split() if part.strip()]


def find_or_create_thread(
    db: Session,
    *,
    owner_user_id: uuid.UUID,
    message_id: str,
    in_reply_to: str,
    references_header: str,
    subject: str,
    participants: list[str],
) -> MailThread:
    ids = []
    if in_reply_to:
        ids.append(in_reply_to)
    ids.extend(split_references(references_header))
    ids = [i for i in ids if i]
    if ids:
        row = db.scalar(
            select(MailMessage)
            .join(MailThread, MailMessage.thread_id == MailThread.id)
            .where(
                MailMessage.message_id_header.in_(ids),
                MailThread.owner_user_id == owner_user_id,
            )
            .limit(1)
        )
        if row:
            thread = db.get(MailThread, row.thread_id)
            if thread:
                return thread
    if message_id:
        row = db.scalar(
            select(MailMessage)
            .join(MailThread, MailMessage.thread_id == MailThread.id)
            .where(
                MailMessage.message_id_header == message_id,
                MailThread.owner_user_id == owner_user_id,
            )
            .limit(1)
        )
        if row:
            thread = db.get(MailThread, row.thread_id)
            if thread:
                return thread
    subj = normalize_subject(subject)
    people = participant_key(participants)
    if subj and people:
        thread = db.scalar(
            select(MailThread).where(
                MailThread.owner_user_id == owner_user_id,
                MailThread.subject_normalized == subj,
                MailThread.participants == people,
            ).limit(1)
        )
        if thread:
            return thread
    thread = MailThread(
        owner_user_id=owner_user_id,
        subject_normalized=subj,
        participants=people,
        last_message_at=datetime.now(timezone.utc),
    )
    db.add(thread)
    db.flush()
    return thread
