from __future__ import annotations

import hashlib
import logging
import re
import uuid
from datetime import datetime, timezone
from email.message import Message
from email.utils import getaddresses, parsedate_to_datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import KnowledgeItem, MailAccount, MailAttachment, MailMessage
from app.threads import find_or_create_thread, normalize_message_id

log = logging.getLogger("ohimymind.store")

_UNSAFE = re.compile(r"[^A-Za-z0-9._-]+")


def safe_filename(name: str) -> str:
    base = Path(name or "attachment").name
    cleaned = _UNSAFE.sub("_", base).strip("._") or "attachment"
    return cleaned[:180]


def decode_header_value(msg: Message, header: str) -> str:
    raw = msg.get(header)
    if raw is None:
        return ""
    try:
        from email.header import decode_header, make_header

        return str(make_header(decode_header(str(raw))))
    except Exception:
        return str(raw)


def _addresses(msg: Message, header: str) -> list[str]:
    pairs = getaddresses(msg.get_all(header, []))
    result = []
    for name, addr in pairs:
        if addr:
            result.append(addr)
        elif name:
            result.append(name)
    return result


def html_to_text(html: str) -> str:
    text = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", html)
    text = re.sub(r"(?i)<br\s*/?>", "\n", text)
    text = re.sub(r"(?i)</p>", "\n", text)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def parse_payload(msg: Message) -> tuple[str, str, list[tuple[str, str, bytes, str]]]:
    body_text = ""
    body_html = ""
    attachments: list[tuple[str, str, bytes, str]] = []

    def walk(part: Message) -> None:
        nonlocal body_text, body_html
        content_type = (part.get_content_type() or "").lower()
        disposition = str(part.get("Content-Disposition") or "").lower()
        filename = part.get_filename()
        content_id = normalize_message_id(str(part.get("Content-ID") or ""))
        payload = part.get_payload(decode=True)
        if part.is_multipart():
            for child in part.get_payload():
                if isinstance(child, Message):
                    walk(child)
            return
        is_file = bool(filename) or "attachment" in disposition or "inline" in disposition
        is_image = content_type.startswith("image/")
        if (is_file or is_image or content_id) and content_type not in {"text/plain", "text/html"}:
            data = payload if isinstance(payload, (bytes, bytearray)) else b""
            name = filename or (f"inline-{content_id}" if content_id else "inline")
            attachments.append(
                (name, content_type or "application/octet-stream", bytes(data), content_id)
            )
            return
        if payload is None:
            return
        charset = part.get_content_charset() or "utf-8"
        try:
            text = payload.decode(charset, errors="replace")
        except Exception:
            text = payload.decode("utf-8", errors="replace")
        if content_type == "text/html" and not body_html:
            body_html = text
        elif content_type == "text/plain" and not body_text:
            body_text = text

    walk(msg)
    if body_html and not body_text:
        body_text = html_to_text(body_html)
    return body_text, body_html, attachments


def rewrite_cids(html: str, attachments: list[MailAttachment]) -> str:
    if not html:
        return html
    out = html
    for att in attachments:
        cid = (att.content_id or "").strip().strip("<>")
        if not cid:
            continue
        url = f"/api/v1/mail/attachments/{att.id}"
        out = re.sub(r"(?i)cid:" + re.escape(cid), url, out)
    return out


def message_sent_at(msg: Message) -> datetime:
    raw = msg.get("Date")
    if raw:
        try:
            dt = parsedate_to_datetime(raw)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except Exception:
            pass
    return datetime.now(timezone.utc)


def flag_list(raw_flags: object) -> list[str]:
    flags: list[str] = []
    if not raw_flags:
        return flags
    for item in raw_flags:
        if isinstance(item, bytes):
            item = item.decode("utf-8", errors="replace")
        text = str(item)
        if not text.startswith("\\"):
            text = "\\" + text if text in {"Seen", "Flagged", "Deleted", "Draft", "Answered"} else text
        flags.append(text)
    return flags


def upsert_parsed_message(
    db: Session,
    *,
    account: MailAccount,
    folder_canonical: str,
    uid: int | None,
    msg: Message,
    raw_flags: object,
) -> MailMessage:
    message_id = normalize_message_id(decode_header_value(msg, "Message-ID"))
    in_reply_to = normalize_message_id(decode_header_value(msg, "In-Reply-To"))
    references_header = decode_header_value(msg, "References")
    subject = decode_header_value(msg, "Subject")
    from_addr = (_addresses(msg, "From") or [""])[0]
    to_addrs = _addresses(msg, "To")
    cc_addrs = _addresses(msg, "Cc")
    body_text, body_html, files = parse_payload(msg)
    flags = flag_list(raw_flags)
    sent_at = message_sent_at(msg)

    existing = None
    if uid is not None:
        existing = db.scalar(
            select(MailMessage).where(
                MailMessage.account_id == account.id,
                MailMessage.folder_canonical == folder_canonical,
                MailMessage.uid == uid,
            )
        )
    if existing is None and message_id:
        existing = db.scalar(
            select(MailMessage).where(
                MailMessage.account_id == account.id,
                MailMessage.message_id_header == message_id,
            )
        )

    participants = [from_addr, *to_addrs, *cc_addrs]
    thread = find_or_create_thread(
        db,
        owner_user_id=account.owner_user_id,
        message_id=message_id,
        in_reply_to=in_reply_to,
        references_header=references_header,
        subject=subject,
        participants=participants,
    )
    if sent_at and (thread.last_message_at is None or sent_at > thread.last_message_at):
        thread.last_message_at = sent_at

    if existing is None:
        item = KnowledgeItem(
            stream_kind="mail",
            owner_user_id=account.owner_user_id,
            embedding=None,
        )
        db.add(item)
        db.flush()
        existing = MailMessage(
            knowledge_item_id=item.id,
            account_id=account.id,
            thread_id=thread.id,
            folder_canonical=folder_canonical,
            uid=uid,
        )
        db.add(existing)
        db.flush()
    else:
        existing.thread_id = thread.id
        existing.folder_canonical = folder_canonical
        if uid is not None:
            existing.uid = uid
        item = existing.knowledge_item
        item.updated_at = datetime.now(timezone.utc)
        item.embedding = None

    existing.message_id_header = message_id
    existing.in_reply_to = in_reply_to
    existing.references_header = references_header
    existing.subject = subject
    existing.from_addr = from_addr
    existing.to_json = to_addrs
    existing.cc_json = cc_addrs
    existing.body_text = body_text
    existing.body_html = body_html
    existing.flags = flags
    existing.sent_at = sent_at
    existing.pending_imap = None
    db.flush()

    if files:
        _store_attachments(db, account.id, existing, files)
        db.flush()
    atts = list(
        db.scalars(select(MailAttachment).where(MailAttachment.message_id == existing.id))
    )
    existing.body_html = rewrite_cids(existing.body_html, atts)
    return existing


def _store_attachments(
    db: Session,
    account_id: uuid.UUID,
    message: MailMessage,
    files: list[tuple[str, str, bytes, str]],
) -> None:
    for att in list(message.attachments):
        db.delete(att)
    db.flush()
    errors = []
    used_names: set[str] = set()
    for filename, mime, data, content_id in files:
        digest = hashlib.sha256(data).hexdigest()
        name = safe_filename(filename)
        if name in used_names:
            name = f"{digest[:8]}_{name}"
        used_names.add(name)
        uid_part = str(message.uid if message.uid is not None else message.id)
        rel_dir = Path(str(account_id)) / uid_part
        abs_dir = Path(settings.attachments_dir) / rel_dir
        try:
            abs_dir.mkdir(parents=True, exist_ok=True)
            abs_path = abs_dir / name
            abs_path.write_bytes(data)
        except OSError:
            log.exception("attachment write failed account_id=%s message_id=%s", account_id, message.id)
            errors.append(name)
            continue
        rel_path = str(rel_dir / name)
        db.add(
            MailAttachment(
                message_id=message.id,
                filename=name,
                mime=mime or "application/octet-stream",
                size_bytes=len(data),
                sha256=digest,
                storage_path=rel_path,
                content_id=content_id or "",
            )
        )
    message.sync_error = "attachment_write_failed" if errors else None
