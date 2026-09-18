from __future__ import annotations

import logging
from datetime import datetime, timezone
from email.parser import BytesParser
from email.policy import default

from imapclient import DELETED, DRAFT, FLAGGED, SEEN, IMAPClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import MailAccount, MailMessage, MailOutbox
from app.store_mail import drop_inbox_copies, upsert_parsed_message
from worker.imap_io import build_outgoing, smtp_connect

log = logging.getLogger("ohimymind.actions")


def apply_pending(client: IMAPClient, db: Session, account: MailAccount, maps: dict[str, str]) -> None:
    rows = list(
        db.scalars(
            select(MailMessage).where(
                MailMessage.account_id == account.id,
                MailMessage.pending_imap.is_not(None),
            )
        )
    )
    for msg in rows:
        action = msg.pending_imap
        try:
            _run_action(client, db, maps, account, msg, action)
            if action == "append_draft" and msg.uid is None:
                pass
            msg.pending_imap = None
        except Exception:
            log.exception("imap action failed account_id=%s message_id=%s action=%s", account.id, msg.id, action)
    if account.pending_empty_trash:
        trash = maps.get("trash")
        if trash:
            try:
                client.select_folder(trash)
                client.expunge()
            except Exception:
                log.exception("expunge failed account_id=%s", account.id)
        account.pending_empty_trash = False


def _run_action(
    client: IMAPClient,
    db: Session,
    maps: dict[str, str],
    account: MailAccount,
    msg: MailMessage,
    action: str,
) -> None:
    if action == "append_draft":
        drafts = maps.get("drafts")
        if not drafts:
            return
        outgoing = build_outgoing(
            from_addr=account.email,
            to_addrs=list(msg.to_json or []),
            cc_addrs=list(msg.cc_json or []),
            subject=msg.subject,
            body_html=msg.body_html,
            in_reply_to=msg.in_reply_to,
            references=msg.references_header,
        )
        result = client.append(drafts, outgoing.as_bytes(), flags=[DRAFT])
        uid = _append_uid(result)
        if uid is not None:
            msg.uid = uid
        return

    kind, _, source_canonical = action.partition(":")
    if msg.uid is None:
        return
    if kind in {"trash", "archive"}:
        source_folder = maps.get(source_canonical or "inbox") or maps.get("inbox")
    else:
        source_folder = maps.get(msg.folder_canonical) or maps.get("inbox")
    if not source_folder:
        return
    try:
        client.select_folder(source_folder)
    except Exception:
        client.select_folder(maps.get("inbox", "INBOX"))

    uid = [msg.uid]
    action = kind
    if action == "trash":
        trash = maps.get("trash")
        if trash:
            try:
                client.copy(uid, trash)
            except Exception:
                log.info("copy to trash failed account_id=%s uid=%s", account.id, msg.uid)
        client.add_flags(uid, [DELETED])
        drop_inbox_copies(db, account.id, msg.message_id_header, keep_id=msg.id)
        return
    if action == "archive":
        if account.provider == "gmail":
            try:
                client.remove_gmail_labels(uid, ["\\Inbox"])
            except Exception:
                log.info("gmail archive labels failed account_id=%s uid=%s", account.id, msg.uid)
                for all_mail in ("[Gmail]/All Mail", "[Gmail]/Вся почта", "[Google Mail]/All Mail"):
                    try:
                        client.move(uid, all_mail)
                        break
                    except Exception:
                        continue
        else:
            archive = maps.get("archive")
            if archive:
                try:
                    client.move(uid, archive)
                except Exception:
                    client.copy(uid, archive)
                    client.add_flags(uid, [DELETED])
        drop_inbox_copies(db, account.id, msg.message_id_header, keep_id=msg.id)
        return
    if action == "set_seen":
        client.add_flags(uid, [SEEN])
    elif action == "clear_seen":
        client.remove_flags(uid, [SEEN])
    elif action == "set_flagged":
        client.add_flags(uid, [FLAGGED])
    elif action == "clear_flagged":
        client.remove_flags(uid, [FLAGGED])


def _append_uid(result: object) -> int | None:
    if isinstance(result, tuple) and len(result) >= 3:
        try:
            return int(result[2])
        except (TypeError, ValueError):
            return None
    return None


def process_outbox(client: IMAPClient, db: Session, account: MailAccount, secret: dict, maps: dict[str, str]) -> None:
    rows = list(
        db.scalars(
            select(MailOutbox).where(
                MailOutbox.account_id == account.id,
                MailOutbox.status == "pending",
            ).order_by(MailOutbox.created_at)
        )
    )
    for row in rows:
        try:
            outgoing = build_outgoing(
                from_addr=account.email,
                to_addrs=list(row.to_json or []),
                cc_addrs=list(row.cc_json or []),
                subject=row.subject,
                body_html=row.body_html,
                in_reply_to=row.in_reply_to_header,
                references=row.references_header,
            )
            recipients = list(row.to_json or []) + list(row.cc_json or [])
            smtp = smtp_connect(account, secret)
            try:
                smtp.send_message(outgoing, from_addr=account.email, to_addrs=recipients)
            finally:
                try:
                    smtp.quit()
                except Exception:
                    pass
            sent_name = maps.get("sent")
            uid = None
            if sent_name:
                result = client.append(sent_name, outgoing.as_bytes(), flags=[SEEN])
                uid = _append_uid(result)
            parsed = BytesParser(policy=default).parsebytes(outgoing.as_bytes())
            stored = upsert_parsed_message(
                db,
                account=account,
                folder_canonical="sent",
                uid=uid,
                msg=parsed,
                raw_flags=["\\Seen"],
            )
            stored.sent_at = datetime.now(timezone.utc)
            row.status = "sent"
            row.sent_at = datetime.now(timezone.utc)
            row.error_text = None
            log.info("outbox sent id=%s account_id=%s", row.id, account.id)
        except Exception as exc:
            row.status = "failed"
            row.error_text = type(exc).__name__
            log.exception("outbox send failed id=%s account_id=%s", row.id, account.id)
