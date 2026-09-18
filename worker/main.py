from __future__ import annotations

import logging
import subprocess
import sys
import threading
import time
import uuid

from sqlalchemy import select

from app.bootstrap import startup
from app.crypto import decrypt_secret
from app.db import SessionLocal
from app.models import MailAccount, MailAccountSecret
from app.providers import CANONICAL_ORDER, should_skip
from worker.actions import apply_pending, process_outbox
from worker.folders import refresh_folder_maps
from worker.imap_io import imap_connect
from worker.sync import sync_folder

log = logging.getLogger("ohimymind.worker")
_stop = threading.Event()
_threads: dict[str, threading.Thread] = {}
_delays: dict[str, float] = {}


def _account_loop(account_id: str) -> None:
    delay = _delays.get(account_id, 5.0)
    aid = uuid.UUID(account_id)
    while not _stop.is_set():
        db = SessionLocal()
        client = None
        try:
            account = db.get(MailAccount, aid)
            if account is None or not account.is_active:
                return
            secret_row = db.get(MailAccountSecret, account.id)
            if secret_row is None:
                log.info("no secret account_id=%s", account.id)
                _stop.wait(delay)
                continue
            secret = decrypt_secret(bytes(secret_row.blob))
            client = imap_connect(account, secret)
            log.info("imap connected email=%s", account.email)
            maps = refresh_folder_maps(client, db, account)
            db.commit()
            log.info("folder maps n=%s email=%s", len(maps), account.email)
            apply_pending(client, db, account, maps)
            process_outbox(client, db, account, secret, maps)
            db.commit()
            inbox = maps.get("inbox", "INBOX")
            sync_folder(client, db, account, "inbox", inbox)
            db.commit()
            last_sweep = time.time()
            delay = 5.0
            _delays[account_id] = delay
            while not _stop.is_set():
                account = db.get(MailAccount, aid)
                if account is None or not account.is_active:
                    return
                secret_row = db.get(MailAccountSecret, account.id)
                if secret_row is None:
                    break
                secret = decrypt_secret(bytes(secret_row.blob))
                apply_pending(client, db, account, maps)
                process_outbox(client, db, account, secret, maps)
                db.commit()
                sync_folder(client, db, account, "inbox", maps.get("inbox", "INBOX"))
                db.commit()
                now = time.time()
                if now - last_sweep >= 60:
                    for canonical, imap_name in list(maps.items()):
                        if canonical == "inbox":
                            continue
                        if should_skip(imap_name):
                            continue
                        limit = 80 if canonical in CANONICAL_ORDER else 20
                        sync_folder(client, db, account, canonical, imap_name, fetch_limit=limit)
                    last_sweep = time.time()
                    db.commit()
                caps = []
                try:
                    caps = list(client.capabilities())
                except Exception:
                    caps = []
                idle_ok = any(
                    (c.decode("utf-8", errors="replace") if isinstance(c, bytes) else str(c)).upper() == "IDLE"
                    for c in caps
                )
                try:
                    client.select_folder(maps.get("inbox", "INBOX"))
                    if idle_ok:
                        client.idle()
                        try:
                            client.idle_check(timeout=30)
                        finally:
                            client.idle_done()
                    else:
                        _stop.wait(30)
                    sync_folder(client, db, account, "inbox", maps.get("inbox", "INBOX"))
                    db.commit()
                except Exception:
                    log.exception("idle loop account_id=%s", account.id)
                    break
        except Exception:
            log.exception("account loop error account_id=%s", account_id)
            try:
                db.rollback()
            except Exception:
                pass
            delay = min(max(delay, 5.0) * 2, 60.0)
            _delays[account_id] = delay
            _stop.wait(delay)
        finally:
            if client is not None:
                try:
                    client.logout()
                except Exception:
                    try:
                        client.shutdown()
                    except Exception:
                        pass
            db.close()


def _reap() -> None:
    dead = [key for key, thread in list(_threads.items()) if not thread.is_alive()]
    for key in dead:
        _threads.pop(key, None)


def main() -> None:
    startup()
    subprocess.check_call([sys.executable, "-m", "alembic", "upgrade", "head"])
    log.info("worker started")
    while not _stop.is_set():
        db = SessionLocal()
        try:
            ids = [str(a.id) for a in db.scalars(select(MailAccount).where(MailAccount.is_active.is_(True)))]
        finally:
            db.close()
        _reap()
        for account_id in ids:
            thread = _threads.get(account_id)
            if thread is None or not thread.is_alive():
                started = threading.Thread(
                    target=_account_loop,
                    args=(account_id,),
                    name=f"imap-{account_id[:8]}",
                    daemon=True,
                )
                _threads[account_id] = started
                started.start()
        _stop.wait(5)


if __name__ == "__main__":
    main()
