from __future__ import annotations

import logging
from email.parser import BytesParser
from email.policy import default

from imapclient import IMAPClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import MailAccount, MailMessage
from app.store_mail import upsert_parsed_message

log = logging.getLogger("ohimymind.sync")


def sync_folder(
    client: IMAPClient,
    db: Session,
    account: MailAccount,
    canonical: str,
    imap_name: str,
) -> None:
    try:
        client.select_folder(imap_name, readonly=True)
    except Exception:
        log.info("select failed account_id=%s folder=%s", account.id, canonical)
        return
    try:
        uids = client.search(["ALL"])
    except Exception:
        log.exception("search failed account_id=%s folder=%s", account.id, canonical)
        return
    uids = [int(u) for u in uids]
    state = dict(account.sync_state or {})
    folder_state = dict(state.get(canonical) or {})
    last_uid = int(folder_state.get("last_uid") or 0)
    existing_uids = set(
        db.scalars(
            select(MailMessage.uid).where(
                MailMessage.account_id == account.id,
                MailMessage.folder_canonical == canonical,
                MailMessage.uid.is_not(None),
            )
        )
    )
    missing = [u for u in uids if u not in existing_uids]
    new_only = [u for u in missing if u > last_uid] or missing
    cid_uids = [
        int(u)
        for u in db.scalars(
            select(MailMessage.uid).where(
                MailMessage.account_id == account.id,
                MailMessage.folder_canonical == canonical,
                MailMessage.uid.is_not(None),
                MailMessage.body_html.ilike("%cid:%"),
            )
        )
        if u is not None
    ]
    to_fetch = list(dict.fromkeys([*new_only, *cid_uids]))
    if to_fetch:
        _fetch_bodies(client, db, account, canonical, to_fetch)
    stale = [u for u in uids if u in existing_uids]
    if stale:
        _refresh_flags(client, db, account, canonical, stale[-400:])
    if uids:
        folder_state["last_uid"] = max(uids)
        state[canonical] = folder_state
        account.sync_state = state


def _fetch_bodies(
    client: IMAPClient,
    db: Session,
    account: MailAccount,
    canonical: str,
    uids: list[int],
) -> None:
    for chunk in _chunks(uids, 25):
        try:
            fetched = client.fetch(chunk, ["RFC822", "FLAGS"])
        except Exception:
            log.exception("fetch failed account_id=%s folder=%s", account.id, canonical)
            continue
        for uid, data in fetched.items():
            raw = data.get(b"RFC822") or data.get("RFC822")
            flags = data.get(b"FLAGS") or data.get("FLAGS") or ()
            flag_txt = [f.decode("utf-8", errors="replace") if isinstance(f, bytes) else str(f) for f in flags]
            if canonical == "inbox" and any(f.lower() == "\\deleted" for f in flag_txt):
                continue
            if not raw:
                continue
            try:
                parsed = BytesParser(policy=default).parsebytes(raw)
                upsert_parsed_message(
                    db,
                    account=account,
                    folder_canonical=canonical,
                    uid=int(uid),
                    msg=parsed,
                    raw_flags=flags,
                )
                db.commit()
            except Exception:
                log.exception("parse/store failed account_id=%s uid=%s", account.id, uid)
                db.rollback()
        db.commit()


def _refresh_flags(
    client: IMAPClient,
    db: Session,
    account: MailAccount,
    canonical: str,
    uids: list[int],
) -> None:
    try:
        fetched = client.fetch(uids, ["FLAGS"])
    except Exception:
        return
    by_uid = {
        int(row.uid): row
        for row in db.scalars(
            select(MailMessage).where(
                MailMessage.account_id == account.id,
                MailMessage.folder_canonical == canonical,
                MailMessage.uid.in_(uids),
            )
        )
        if row.uid is not None
    }
    for uid, data in fetched.items():
        row = by_uid.get(int(uid))
        if row is None or row.pending_imap:
            continue
        flags = data.get(b"FLAGS") or data.get("FLAGS") or ()
        normalized = []
        for item in flags:
            text = item.decode("utf-8", errors="replace") if isinstance(item, bytes) else str(item)
            if not text.startswith("\\") and text in {"Seen", "Flagged", "Deleted", "Draft", "Answered"}:
                text = "\\" + text
            normalized.append(text)
        row.flags = normalized


def _chunks(items: list[int], size: int) -> list[list[int]]:
    return [items[i : i + size] for i in range(0, len(items), size)]
