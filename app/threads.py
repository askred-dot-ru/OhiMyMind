from __future__ import annotations

import logging
import re
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from typing import Iterable

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models import MailMessage, MailThread

log = logging.getLogger("ohimymind.threads")

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


def collect_ids(message_id: str, in_reply_to: str, references_header: str) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for raw in (message_id, in_reply_to, *split_references(references_header)):
        item = normalize_message_id(raw)
        if item and item not in seen:
            seen.add(item)
            out.append(item)
    return out


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _when(msg: MailMessage) -> datetime:
    return msg.sent_at or msg.created_at


def _utc_min() -> datetime:
    return datetime.min.replace(tzinfo=timezone.utc)


def _messages_touching_ids(
    db: Session,
    owner_user_id: uuid.UUID,
    ids: Iterable[str],
    seen_pks: set[uuid.UUID],
) -> list[MailMessage]:
    id_list = [i for i in ids if i]
    if not id_list:
        return []
    clauses = [
        MailMessage.message_id_header.in_(id_list),
        MailMessage.in_reply_to.in_(id_list),
        *[MailMessage.references_header.like(f"%{_escape_like(i)}%", escape="\\") for i in id_list],
    ]
    stmt = (
        select(MailMessage)
        .join(MailThread, MailMessage.thread_id == MailThread.id)
        .where(MailThread.owner_user_id == owner_user_id, or_(*clauses))
    )
    if seen_pks:
        stmt = stmt.where(MailMessage.id.notin_(seen_pks))
    return list(db.scalars(stmt))


def _linked_messages(
    db: Session,
    owner_user_id: uuid.UUID,
    message_id: str,
    in_reply_to: str,
    references_header: str,
) -> list[MailMessage]:
    known = set(collect_ids(message_id, in_reply_to, references_header))
    seen: set[uuid.UUID] = set()
    found: list[MailMessage] = []
    for _ in range(64):
        if not known:
            break
        batch = _messages_touching_ids(db, owner_user_id, known, seen)
        if not batch:
            break
        for row in batch:
            seen.add(row.id)
            found.append(row)
            known.update(collect_ids(row.message_id_header, row.in_reply_to, row.references_header))
    return found


def _merge_threads(db: Session, threads: list[MailThread]) -> MailThread:
    uniq: dict[uuid.UUID, MailThread] = {}
    for thread in threads:
        if thread is not None:
            uniq[thread.id] = thread
    ordered = sorted(
        uniq.values(),
        key=lambda t: t.last_message_at or _utc_min(),
        reverse=True,
    )
    survivor = ordered[0]
    for thread in ordered[1:]:
        rows = list(db.scalars(select(MailMessage).where(MailMessage.thread_id == thread.id)))
        for msg in rows:
            msg.thread_id = survivor.id
        if thread.last_message_at and (
            survivor.last_message_at is None or thread.last_message_at > survivor.last_message_at
        ):
            survivor.last_message_at = thread.last_message_at
        db.delete(thread)
    db.flush()
    return survivor


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
    linked = _linked_messages(db, owner_user_id, message_id, in_reply_to, references_header)
    threads: list[MailThread] = []
    seen_t: set[uuid.UUID] = set()
    for row in linked:
        if row.thread_id in seen_t:
            continue
        thread = db.get(MailThread, row.thread_id)
        if thread is None:
            continue
        seen_t.add(thread.id)
        threads.append(thread)
    if threads:
        return _merge_threads(db, threads)
    thread = MailThread(
        owner_user_id=owner_user_id,
        subject_normalized=normalize_subject(subject),
        participants=participant_key(participants),
        last_message_at=datetime.now(timezone.utc),
    )
    db.add(thread)
    db.flush()
    return thread


class _UF:
    def __init__(self) -> None:
        self.parent: dict[uuid.UUID, uuid.UUID] = {}

    def add(self, item: uuid.UUID) -> None:
        self.parent.setdefault(item, item)

    def find(self, item: uuid.UUID) -> uuid.UUID:
        while self.parent[item] != item:
            self.parent[item] = self.parent[self.parent[item]]
            item = self.parent[item]
        return item

    def union(self, left: uuid.UUID, right: uuid.UUID) -> None:
        a = self.find(left)
        b = self.find(right)
        if a != b:
            self.parent[b] = a


def rebuild_threads_for_owner(db: Session, owner_user_id: uuid.UUID) -> tuple[int, int, int]:
    messages = list(
        db.scalars(
            select(MailMessage)
            .join(MailThread, MailMessage.thread_id == MailThread.id)
            .where(MailThread.owner_user_id == owner_user_id)
        )
    )
    if not messages:
        orphans = list(db.scalars(select(MailThread).where(MailThread.owner_user_id == owner_user_id)))
        for thread in orphans:
            db.delete(thread)
        db.flush()
        return 0, 0, len(orphans)

    uf = _UF()
    by_id: dict[str, list[uuid.UUID]] = defaultdict(list)
    for msg in messages:
        uf.add(msg.id)
        for ident in collect_ids(msg.message_id_header, msg.in_reply_to, msg.references_header):
            for other in by_id[ident]:
                uf.union(msg.id, other)
            by_id[ident].append(msg.id)

    groups: dict[uuid.UUID, list[MailMessage]] = defaultdict(list)
    for msg in messages:
        groups[uf.find(msg.id)].append(msg)

    components = sorted(groups.values(), key=len, reverse=True)
    claimed: set[uuid.UUID] = set()
    moved = 0
    created = 0
    for group in components:
        counts: dict[uuid.UUID, int] = defaultdict(int)
        for msg in group:
            counts[msg.thread_id] += 1
        survivor_id = None
        for tid, _n in sorted(counts.items(), key=lambda kv: kv[1], reverse=True):
            if tid not in claimed:
                survivor_id = tid
                break
        if survivor_id is None:
            latest = max(group, key=_when)
            people = [latest.from_addr, *(latest.to_json or []), *(latest.cc_json or [])]
            thread = MailThread(
                owner_user_id=owner_user_id,
                subject_normalized=normalize_subject(latest.subject),
                participants=participant_key(people),
                last_message_at=_when(latest),
            )
            db.add(thread)
            db.flush()
            survivor_id = thread.id
            created += 1
        claimed.add(survivor_id)
        thread = db.get(MailThread, survivor_id)
        if thread is not None:
            latest = max(group, key=_when)
            people = [latest.from_addr, *(latest.to_json or []), *(latest.cc_json or [])]
            thread.subject_normalized = normalize_subject(latest.subject)
            thread.participants = participant_key(people)
            thread.last_message_at = max(_when(m) for m in group)
        for msg in group:
            if msg.thread_id != survivor_id:
                msg.thread_id = survivor_id
                moved += 1
    db.flush()
    deleted = 0
    leftover_stmt = select(MailThread).where(MailThread.owner_user_id == owner_user_id)
    if claimed:
        leftover_stmt = leftover_stmt.where(MailThread.id.notin_(list(claimed)))
    leftovers = list(db.scalars(leftover_stmt))
    for thread in leftovers:
        still = db.scalar(select(MailMessage.id).where(MailMessage.thread_id == thread.id).limit(1))
        if still is None:
            db.delete(thread)
            deleted += 1
    db.flush()
    return moved, created, deleted


def rebuild_all_threads(db: Session) -> dict[str, int]:
    owners = list(db.scalars(select(MailThread.owner_user_id).distinct()))
    moved = created = deleted = 0
    for owner in owners:
        a, b, c = rebuild_threads_for_owner(db, owner)
        moved += a
        created += b
        deleted += c
    log.info("rethread identifier-only moved=%s created=%s deleted=%s", moved, created, deleted)
    return {"moved": moved, "created": created, "deleted": deleted}
