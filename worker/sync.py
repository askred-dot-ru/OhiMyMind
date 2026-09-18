from __future__ import annotations

import logging
from email.parser import BytesParser
from email.policy import default

from imapclient import IMAPClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import MailAccount, MailMessage
from app.store_mail import parked_uids, purge_parked_from_inbox, upsert_parsed_message

log = logging.getLogger("ohimymind.sync")

INBOX_FETCH_CAP = 100
OTHER_FETCH_CAP = 40


def _search_uids(client: IMAPClient, criteria: list) -> list[int]:
    try:
        return [int(u) for u in client.search(criteria)]
    except Exception:
        log.exception("search %s failed", criteria)
        return []


def _existing_uids(db: Session, account: MailAccount, canonical: str) -> set[int]:
    return set(
        db.scalars(
            select(MailMessage.uid).where(
                MailMessage.account_id == account.id,
                MailMessage.folder_canonical == canonical,
                MailMessage.uid.is_not(None),
            )
        )
    )


def sync_folder(
    client: IMAPClient,
    db: Session,
    account: MailAccount,
    canonical: str,
    imap_name: str,
    fetch_limit: int | None = None,
) -> None:
    try:
        sel = client.select_folder(imap_name, readonly=True)
    except Exception:
        log.info("select failed account_id=%s folder=%s", account.id, canonical)
        return
    uidnext = int(sel.get(b"UIDNEXT") or sel.get("UIDNEXT") or 0)
    state = dict(account.sync_state or {})
    folder_state = dict(state.get(canonical) or {})
    last_uid = int(folder_state.get("last_uid") or 0)
    existing = _existing_uids(db, account, canonical)
    cap = fetch_limit if fetch_limit is not None else (INBOX_FETCH_CAP if canonical == "inbox" else OTHER_FETCH_CAP)

    to_fetch: list[int] = []
    if last_uid > 0:
        newer = [u for u in _search_uids(client, [f"{last_uid + 1}:*"]) if u > last_uid]
        to_fetch.extend(u for u in newer if u not in existing)
        if newer:
            last_uid = max(last_uid, max(newer))
    elif canonical != "inbox":
        to_fetch.extend(u for u in _search_uids(client, ["ALL"]) if u not in existing)

    if canonical == "inbox":
        unseen = _search_uids(client, ["UNSEEN"])
        to_fetch.extend(u for u in unseen if u not in existing)
        if uidnext:
            window_start = max(1, uidnext - 400)
            window = _search_uids(client, [f"{window_start}:*"])
            to_fetch.extend(u for u in window if u not in existing)
        n = purge_parked_from_inbox(db, account.id)
        if n:
            log.info("dropped parked inbox copies n=%s account_id=%s", n, account.id)
            db.commit()
        skipped = parked_uids(db, account.id)
        to_fetch = [u for u in to_fetch if u not in skipped]

    seen: set[int] = set()
    ordered: list[int] = []
    for uid in sorted(to_fetch, reverse=True):
        if uid in seen:
            continue
        seen.add(uid)
        ordered.append(uid)
    ordered = ordered[:cap]
    if ordered:
        log.info(
            "fetch folder=%s account_id=%s taking=%s max_uid=%s",
            canonical,
            account.id,
            len(ordered),
            max(ordered),
        )
        _fetch_bodies(client, db, account, canonical, ordered)
    if last_uid:
        folder_state["last_uid"] = last_uid
        state[canonical] = folder_state
        account.sync_state = state
    elif ordered:
        folder_state["last_uid"] = max(ordered)
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
            except Exception as exc:
                log.warning(
                    "parse/store failed account_id=%s uid=%s err=%s",
                    account.id,
                    uid,
                    type(exc).__name__,
                )
                db.rollback()


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
