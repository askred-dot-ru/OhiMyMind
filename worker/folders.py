from __future__ import annotations

import logging

from imapclient import IMAPClient
from sqlalchemy.orm import Session

from app.models import MailAccount, MailFolderMap
from app.providers import (
    CANONICAL_ORDER,
    is_gmail_system_folder,
    match_canonical,
    normalize_user_canonical,
    should_skip,
)

log = logging.getLogger("ohimymind.folders")


def _folder_name(entry) -> str:
    if isinstance(entry, tuple) and len(entry) >= 3:
        name = entry[2]
    else:
        name = entry
    if isinstance(name, bytes):
        name = name.decode("utf-8", errors="replace")
    return str(name)


def _flags(entry) -> list:
    if isinstance(entry, tuple) and entry:
        return list(entry[0] or [])
    return []


def refresh_folder_maps(client: IMAPClient, db: Session, account: MailAccount) -> dict[str, str]:
    listed = client.list_folders()
    mapping: dict[str, str] = {}
    for entry in listed:
        name = _folder_name(entry)
        flags = _flags(entry)
        flag_txt = [f.decode("utf-8", errors="replace") if isinstance(f, bytes) else str(f) for f in flags]
        if should_skip(name):
            continue
        if any(f.lower() == "\\noselect" for f in flag_txt):
            continue
        canonical = match_canonical(account.provider, name)
        if canonical is None:
            canonical = normalize_user_canonical(name)
        if canonical in mapping and canonical in CANONICAL_ORDER:
            prev = mapping[canonical]
            if is_gmail_system_folder(name) and not is_gmail_system_folder(prev):
                mapping[canonical] = name
            continue
        mapping[canonical] = name

    if account.provider == "yandex" and "archive" not in mapping:
        try:
            client.create_folder("Archive")
            mapping["archive"] = "Archive"
        except Exception:
            log.info("archive folder create skipped account_id=%s", account.id)

    existing = {row.canonical: row for row in account.folder_maps}
    for canonical, imap_name in mapping.items():
        row = existing.get(canonical)
        if row is None:
            row = MailFolderMap(account_id=account.id, canonical=canonical, imap_name=imap_name)
            db.add(row)
            account.folder_maps.append(row)
        else:
            row.imap_name = imap_name
    for row in list(account.folder_maps):
        if row.canonical in mapping and not should_skip(row.imap_name):
            continue
        db.delete(row)
    db.flush()
    db.expire(account, ["folder_maps"])
    return {m.canonical: m.imap_name for m in account.folder_maps}
