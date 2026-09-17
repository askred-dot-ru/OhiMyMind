from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import FileResponse, RedirectResponse
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session, selectinload

from app.config import settings
from app.crypto import encrypt_secret
from app.db import get_db
from app.deps import current_user, owner_scope
from app.gmail_oauth import authorization_url, build_flow, redirect_uri, redirect_uri_for_request
from app.models import (
    KnowledgeItem,
    MailAccount,
    MailAccountSecret,
    MailAttachment,
    MailMessage,
    MailOutbox,
    MailThread,
    User,
)
from app.providers import CANONICAL_ORDER, PROVIDER_DEFAULTS, display_name
from app.schemas import (
    AccountOut,
    AccountPatchIn,
    AttachmentMeta,
    ComposeIn,
    FolderNode,
    FolderTree,
    MessageOut,
    ThreadFlagsIn,
    ThreadHead,
    ThreadOut,
    YandexAccountIn,
)
from app.security import dump_oauth_state, load_oauth_state
from app.store_mail import html_to_text, rewrite_cids
from app.threads import normalize_message_id

router = APIRouter()


def _account_out(row: MailAccount) -> AccountOut:
    return AccountOut(
        id=row.id,
        provider=row.provider,
        email=row.email,
        unified=row.unified,
        is_default_compose=row.is_default_compose,
        imap_host=row.imap_host,
        smtp_host=row.smtp_host,
    )


def _owned_account(db: Session, account_id: uuid.UUID, user: User) -> MailAccount:
    account = db.get(MailAccount, account_id)
    if account is None or not account.is_active:
        raise HTTPException(status_code=404, detail="account_not_found")
    if account.owner_user_id != user.id:
        raise HTTPException(status_code=403, detail="forbidden")
    return account


def _clear_default(db: Session, owner_id: uuid.UUID, except_id: uuid.UUID | None = None) -> None:
    rows = db.scalars(select(MailAccount).where(MailAccount.owner_user_id == owner_id, MailAccount.is_default_compose))
    for row in rows:
        if except_id is not None and row.id == except_id:
            continue
        row.is_default_compose = False


def _maybe_default(db: Session, account: MailAccount) -> None:
    other = db.scalar(
        select(MailAccount.id).where(
            MailAccount.owner_user_id == account.owner_user_id,
            MailAccount.is_active.is_(True),
            MailAccount.is_default_compose.is_(True),
            MailAccount.id != account.id,
        )
    )
    if other is None:
        account.is_default_compose = True


def _iso(dt) -> str | None:
    return dt.isoformat() if dt is not None else None


def _provider_map(db: Session, account_ids: list[uuid.UUID]) -> dict[uuid.UUID, str]:
    ids = {i for i in account_ids if i is not None}
    if not ids:
        return {}
    rows = db.scalars(select(MailAccount).where(MailAccount.id.in_(ids)))
    return {row.id: row.provider for row in rows}


@router.get("/mail/accounts", response_model=list[AccountOut])
def list_accounts(user: User = Depends(current_user), db: Session = Depends(get_db)) -> list[AccountOut]:
    rows = db.scalars(
        select(MailAccount)
        .where(MailAccount.owner_user_id == user.id, MailAccount.is_active.is_(True))
        .order_by(MailAccount.created_at)
    )
    return [_account_out(r) for r in rows]


@router.post("/mail/accounts", response_model=AccountOut, status_code=201)
def create_account(
    payload: YandexAccountIn,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> AccountOut:
    if payload.provider != "yandex":
        raise HTTPException(status_code=400, detail="provider_unsupported")
    defaults = PROVIDER_DEFAULTS["yandex"]
    email = str(payload.email).strip()
    existing = db.scalar(
        select(MailAccount).where(MailAccount.owner_user_id == user.id, MailAccount.email == email)
    )
    if existing and existing.is_active:
        raise HTTPException(status_code=409, detail="account_exists")
    from imapclient import IMAPClient

    host = payload.imap_host or defaults["imap_host"]
    port = payload.imap_port or defaults["imap_port"]
    try:
        with IMAPClient(host, port=port, ssl=True) as client:
            client.login(email, payload.app_password)
    except Exception:
        raise HTTPException(status_code=400, detail="imap_login_failed") from None
    account = existing or MailAccount(owner_user_id=user.id, email=email)
    account.provider = "yandex"
    account.imap_host = host
    account.imap_port = port
    account.smtp_host = payload.smtp_host or defaults["smtp_host"]
    account.smtp_port = payload.smtp_port or defaults["smtp_port"]
    account.use_ssl = True
    account.is_active = True
    db.add(account)
    db.flush()
    secret = db.get(MailAccountSecret, account.id) or MailAccountSecret(account_id=account.id)
    secret.blob = encrypt_secret({"kind": "password", "password": payload.app_password})
    db.add(secret)
    _maybe_default(db, account)
    db.commit()
    db.refresh(account)
    return _account_out(account)


@router.post("/mail/accounts/gmail/start")
def gmail_start(request: Request, user: User = Depends(current_user)) -> dict:
    if not settings.gmail_oauth_configured:
        raise HTTPException(status_code=409, detail="gmail_oauth_not_configured")
    callback = redirect_uri_for_request(request)
    state = dump_oauth_state(str(user.id), callback)
    return {"authorization_url": authorization_url(state, callback), "redirect_uri": callback}


@router.get("/mail/accounts/gmail/callback")
def gmail_callback(code: str = "", state: str = "", db: Session = Depends(get_db)):
    if not settings.gmail_oauth_configured:
        raise HTTPException(status_code=409, detail="gmail_oauth_not_configured")
    user_id, callback = load_oauth_state(state)
    if not user_id or not code:
        raise HTTPException(status_code=400, detail="oauth_state")
    user = db.get(User, uuid.UUID(user_id))
    if user is None:
        raise HTTPException(status_code=401, detail="unauthorized")
    flow = build_flow(state, callback or redirect_uri())
    flow.fetch_token(code=code)
    creds = flow.credentials
    if not creds.refresh_token:
        raise HTTPException(status_code=400, detail="gmail_refresh_token_missing")
    import json
    from urllib.request import Request, urlopen

    req = Request(
        "https://www.googleapis.com/oauth2/v2/userinfo",
        headers={"Authorization": f"Bearer {creds.token}"},
    )
    with urlopen(req, timeout=20) as resp:
        info = json.loads(resp.read().decode("utf-8"))
    email = (info.get("email") or "").strip()
    if not email:
        raise HTTPException(status_code=400, detail="gmail_email_missing")
    defaults = PROVIDER_DEFAULTS["gmail"]
    account = db.scalar(select(MailAccount).where(MailAccount.owner_user_id == user.id, MailAccount.email == email))
    if account is None:
        account = MailAccount(owner_user_id=user.id, email=email)
        db.add(account)
    account.provider = "gmail"
    account.imap_host = defaults["imap_host"]
    account.imap_port = defaults["imap_port"]
    account.smtp_host = defaults["smtp_host"]
    account.smtp_port = defaults["smtp_port"]
    account.use_ssl = True
    account.is_active = True
    db.flush()
    secret = db.get(MailAccountSecret, account.id) or MailAccountSecret(account_id=account.id)
    secret.blob = encrypt_secret({"kind": "oauth", "refresh_token": creds.refresh_token})
    db.add(secret)
    _maybe_default(db, account)
    db.commit()
    return RedirectResponse(settings.public_base_url.rstrip("/") + "/settings?gmail=ok", status_code=302)


@router.patch("/mail/accounts/{account_id}", response_model=AccountOut)
def patch_account(
    account_id: uuid.UUID,
    payload: AccountPatchIn,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> AccountOut:
    account = _owned_account(db, account_id, user)
    if payload.unified is not None:
        account.unified = payload.unified
    if payload.is_default_compose is True:
        _clear_default(db, user.id, except_id=account.id)
        account.is_default_compose = True
    elif payload.is_default_compose is False:
        has_other = db.scalar(
            select(MailAccount.id).where(
                MailAccount.owner_user_id == user.id,
                MailAccount.is_active.is_(True),
                MailAccount.is_default_compose.is_(True),
                MailAccount.id != account.id,
            )
        )
        if has_other:
            account.is_default_compose = False
    db.commit()
    db.refresh(account)
    return _account_out(account)


@router.get("/mail/folders", response_model=list[FolderTree])
def list_folders(
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
    as_user_id: uuid.UUID | None = Query(default=None),
) -> list[FolderTree]:
    owner_id = owner_scope(user, as_user_id)
    stmt = select(MailAccount).options(selectinload(MailAccount.folder_maps)).where(MailAccount.is_active.is_(True))
    if owner_id is not None:
        stmt = stmt.where(MailAccount.owner_user_id == owner_id)
    accounts = list(db.scalars(stmt))
    trees: list[FolderTree] = []

    def nodes_for(accs: list[MailAccount], with_account: bool) -> list[FolderNode]:
        seen: dict[str, FolderNode] = {}
        for acc in accs:
            names = {m.canonical: m.imap_name for m in acc.folder_maps}
            for canonical in CANONICAL_ORDER:
                if canonical not in seen:
                    seen[canonical] = FolderNode(
                        id=canonical if not with_account else f"{acc.id}:{canonical}",
                        canonical=canonical,
                        name=display_name(canonical),
                        account_id=acc.id if with_account else None,
                    )
            for canonical in names:
                if canonical in seen:
                    continue
                seen[canonical] = FolderNode(
                    id=canonical if not with_account else f"{acc.id}:{canonical}",
                    canonical=canonical,
                    name=display_name(canonical),
                    account_id=acc.id if with_account else None,
                )
        ordered = [seen[c] for c in CANONICAL_ORDER if c in seen]
        extra = [v for k, v in seen.items() if k not in CANONICAL_ORDER]
        extra.sort(key=lambda n: n.name.casefold())
        return ordered + extra

    unified = [a for a in accounts if a.unified]
    split = [a for a in accounts if not a.unified]
    if unified:
        trees.append(FolderTree(kind="unified", label=None, folders=nodes_for(unified, False)))
    for acc in split:
        trees.append(FolderTree(kind="split", label=str(acc.email), folders=nodes_for([acc], True)))
    return trees


def _thread_heads(
    db: Session,
    *,
    owner_id: uuid.UUID | None,
    folder: str,
    q: str | None,
    account_id: uuid.UUID | None,
) -> list[ThreadHead]:
    folder_last = func.max(MailMessage.sent_at)
    stmt = (
        select(MailThread)
        .join(MailMessage, MailMessage.thread_id == MailThread.id)
        .where(MailMessage.folder_canonical == folder)
    )
    if owner_id is not None:
        stmt = stmt.where(MailThread.owner_user_id == owner_id)
    if account_id is not None:
        stmt = stmt.where(MailMessage.account_id == account_id)
    if q:
        stmt = stmt.where(MailMessage.fts.op("@@")(func.plainto_tsquery("simple", q)))
    stmt = (
        stmt.group_by(MailThread.id)
        .order_by(folder_last.desc().nulls_last(), MailThread.id.desc())
        .limit(150)
    )
    threads = list(db.scalars(stmt))
    heads: list[ThreadHead] = []
    for thread in threads:
        msg_stmt = (
            select(MailMessage)
            .where(MailMessage.thread_id == thread.id, MailMessage.folder_canonical == folder)
            .order_by(MailMessage.sent_at.desc().nulls_last(), MailMessage.created_at.desc())
        )
        if account_id is not None:
            msg_stmt = msg_stmt.where(MailMessage.account_id == account_id)
        messages = list(db.scalars(msg_stmt))
        if not messages:
            continue
        latest = messages[0]
        unread = any("\\Seen" not in (m.flags or []) for m in messages)
        flagged = any("\\Flagged" in (m.flags or []) for m in messages)
        snippet = (latest.body_text or html_to_text(latest.body_html) or "")[:180]
        heads.append(
            ThreadHead(
                id=thread.id,
                subject=latest.subject or thread.subject_normalized or "(без темы)",
                from_addr=latest.from_addr,
                snippet=snippet,
                last_at=_iso(latest.sent_at or thread.last_message_at),
                unread=unread,
                flagged=flagged,
                account_id=latest.account_id,
                folder_canonical=folder,
                provider="",
            )
        )
    providers = _provider_map(db, [h.account_id for h in heads])
    for head in heads:
        head.provider = providers.get(head.account_id, "")
    heads.sort(key=lambda h: h.last_at or "", reverse=True)
    return heads


@router.get("/mail/threads", response_model=list[ThreadHead])
def list_threads(
    folder: str = Query(default="inbox"),
    q: str | None = Query(default=None),
    account_id: uuid.UUID | None = Query(default=None),
    as_user_id: uuid.UUID | None = Query(default=None),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> list[ThreadHead]:
    owner_id = owner_scope(user, as_user_id)
    canonical = folder
    acc = account_id
    if ":" in folder and account_id is None:
        prefix, canonical = folder.split(":", 1)
        try:
            acc = uuid.UUID(prefix)
        except ValueError:
            canonical = folder
            acc = None
    return _thread_heads(db, owner_id=owner_id, folder=canonical, q=q, account_id=acc)


def _visible_thread(db: Session, thread_id: uuid.UUID, owner_id: uuid.UUID | None) -> MailThread:
    thread = db.get(MailThread, thread_id)
    if thread is None:
        raise HTTPException(status_code=404, detail="thread_not_found")
    if owner_id is not None and thread.owner_user_id != owner_id:
        raise HTTPException(status_code=404, detail="thread_not_found")
    return thread


@router.get("/mail/threads/{thread_id}", response_model=ThreadOut)
def get_thread(
    thread_id: uuid.UUID,
    as_user_id: uuid.UUID | None = Query(default=None),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> ThreadOut:
    owner_id = owner_scope(user, as_user_id)
    thread = _visible_thread(db, thread_id, owner_id)
    messages = list(
        db.scalars(
            select(MailMessage)
            .options(selectinload(MailMessage.attachments))
            .where(MailMessage.thread_id == thread.id)
            .order_by(MailMessage.sent_at.asc().nulls_last(), MailMessage.created_at.asc())
        )
    )
    providers = _provider_map(db, [msg.account_id for msg in messages])
    out = []
    for msg in messages:
        html = rewrite_cids(msg.body_html, list(msg.attachments))
        shown = [a for a in msg.attachments if not a.content_id]
        out.append(
            MessageOut(
                id=msg.id,
                account_id=msg.account_id,
                provider=providers.get(msg.account_id, ""),
                folder_canonical=msg.folder_canonical,
                subject=msg.subject,
                from_addr=msg.from_addr,
                to=msg.to_json or [],
                cc=msg.cc_json or [],
                sent_at=_iso(msg.sent_at),
                body_text=msg.body_text,
                body_html=html,
                flags=msg.flags or [],
                attachments=[
                    AttachmentMeta(
                        id=a.id,
                        filename=a.filename,
                        mime=a.mime,
                        size_bytes=a.size_bytes,
                        content_id=a.content_id or "",
                    )
                    for a in shown
                ],
            )
        )
    return ThreadOut(id=thread.id, messages=out)


@router.post("/mail/threads/{thread_id}/read")
def flag_thread(
    thread_id: uuid.UUID,
    payload: ThreadFlagsIn,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict:
    thread = _visible_thread(db, thread_id, user.id if user.role != "admin" else None)
    if user.role != "admin" and thread.owner_user_id != user.id:
        raise HTTPException(status_code=404, detail="thread_not_found")
    if user.role == "admin" and thread.owner_user_id != user.id:
        raise HTTPException(status_code=403, detail="forbidden")
    stmt = select(MailMessage).where(MailMessage.thread_id == thread.id)
    if payload.message_id:
        stmt = stmt.where(MailMessage.id == payload.message_id)
    rows = list(db.scalars(stmt))
    for msg in rows:
        flags = list(msg.flags or [])
        if payload.seen is True and "\\Seen" not in flags:
            flags.append("\\Seen")
            msg.pending_imap = "set_seen"
        if payload.seen is False:
            flags = [f for f in flags if f != "\\Seen"]
            msg.pending_imap = "clear_seen"
        if payload.flagged is True and "\\Flagged" not in flags:
            flags.append("\\Flagged")
            msg.pending_imap = "set_flagged"
        if payload.flagged is False:
            flags = [f for f in flags if f != "\\Flagged"]
            msg.pending_imap = "clear_flagged"
        msg.flags = flags
    db.commit()
    return {"ok": True}


@router.post("/mail/messages/{message_id}/trash")
def trash_message(
    message_id: uuid.UUID,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict:
    msg = db.get(MailMessage, message_id)
    if msg is None:
        raise HTTPException(status_code=404, detail="message_not_found")
    account = db.get(MailAccount, msg.account_id)
    if account is None or account.owner_user_id != user.id:
        raise HTTPException(status_code=403, detail="forbidden")
    source = msg.folder_canonical
    msg.folder_canonical = "trash"
    msg.pending_imap = f"trash:{source}"
    db.commit()
    return {"ok": True}


@router.post("/mail/messages/{message_id}/archive")
def archive_message(
    message_id: uuid.UUID,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict:
    msg = db.get(MailMessage, message_id)
    if msg is None:
        raise HTTPException(status_code=404, detail="message_not_found")
    account = db.get(MailAccount, msg.account_id)
    if account is None or account.owner_user_id != user.id:
        raise HTTPException(status_code=403, detail="forbidden")
    source = msg.folder_canonical
    msg.folder_canonical = "archive"
    msg.pending_imap = f"archive:{source}"
    db.commit()
    return {"ok": True}


@router.post("/mail/folders/trash/empty")
def empty_trash(user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    accounts = list(
        db.scalars(select(MailAccount).where(MailAccount.owner_user_id == user.id, MailAccount.is_active.is_(True)))
    )
    ids = [a.id for a in accounts]
    msgs = list(
        db.scalars(select(MailMessage).where(MailMessage.account_id.in_(ids), MailMessage.folder_canonical == "trash"))
        if ids
        else []
    )
    item_ids = [m.knowledge_item_id for m in msgs]
    for acc in accounts:
        acc.pending_empty_trash = True
    if item_ids:
        db.execute(delete(KnowledgeItem).where(KnowledgeItem.id.in_(item_ids)))
    db.commit()
    return {"ok": True}


@router.post("/mail/messages", status_code=202)
def compose(
    payload: ComposeIn,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict:
    account_id = payload.account_id
    in_reply_header = ""
    references_header = ""
    source: MailMessage | None = None
    if payload.in_reply_to or payload.forward_of:
        source_id = payload.in_reply_to or payload.forward_of
        source = db.get(MailMessage, source_id)
        if source is None:
            raise HTTPException(status_code=404, detail="message_not_found")
        src_acc = db.get(MailAccount, source.account_id)
        if src_acc is None or src_acc.owner_user_id != user.id:
            raise HTTPException(status_code=403, detail="forbidden")
        if payload.in_reply_to:
            account_id = source.account_id
            in_reply_header = source.message_id_header
            refs = (source.references_header or "").strip()
            references_header = (refs + " " + source.message_id_header).strip()
    account = db.get(MailAccount, account_id)
    if account is None or not account.is_active:
        raise HTTPException(status_code=404, detail="account_not_found")
    if account.owner_user_id != user.id:
        raise HTTPException(status_code=403, detail="forbidden")
    if payload.draft:
        from datetime import datetime, timezone

        from app.models import KnowledgeItem as KI
        from app.threads import find_or_create_thread

        item = KI(stream_kind="mail", owner_user_id=user.id, embedding=None)
        db.add(item)
        db.flush()
        participants = [account.email, *payload.to, *payload.cc]
        thread = find_or_create_thread(
            db,
            owner_user_id=user.id,
            message_id="",
            in_reply_to=in_reply_header,
            references_header=references_header,
            subject=payload.subject,
            participants=participants,
        )
        draft = MailMessage(
            knowledge_item_id=item.id,
            account_id=account.id,
            thread_id=thread.id,
            folder_canonical="drafts",
            uid=None,
            message_id_header="",
            in_reply_to=in_reply_header,
            references_header=references_header,
            subject=payload.subject,
            from_addr=account.email,
            to_json=payload.to,
            cc_json=payload.cc,
            body_text=html_to_text(payload.body_html),
            body_html=payload.body_html,
            flags=["\\Draft"],
            sent_at=datetime.now(timezone.utc),
            pending_imap="append_draft",
        )
        db.add(draft)
        db.commit()
        return {"id": str(draft.id), "draft": True}
    row = MailOutbox(
        account_id=account.id,
        owner_user_id=user.id,
        to_json=payload.to,
        cc_json=payload.cc,
        subject=payload.subject,
        body_html=payload.body_html,
        in_reply_to_header=normalize_message_id(in_reply_header),
        references_header=references_header,
        status="pending",
    )
    db.add(row)
    db.commit()
    return {"id": str(row.id), "draft": False}


@router.get("/mail/attachments/{attachment_id}")
def download_attachment(
    attachment_id: uuid.UUID,
    as_user_id: uuid.UUID | None = Query(default=None),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    att = db.get(MailAttachment, attachment_id)
    if att is None:
        raise HTTPException(status_code=404, detail="attachment_not_found")
    msg = db.get(MailMessage, att.message_id)
    if msg is None:
        raise HTTPException(status_code=404, detail="attachment_not_found")
    account = db.get(MailAccount, msg.account_id)
    owner_id = owner_scope(user, as_user_id)
    if owner_id is not None and (account is None or account.owner_user_id != owner_id):
        raise HTTPException(status_code=404, detail="attachment_not_found")
    root = Path(settings.attachments_dir).resolve()
    path = (root / att.storage_path).resolve()
    if root not in path.parents and path != root:
        raise HTTPException(status_code=404, detail="attachment_not_found")
    if not path.is_file():
        raise HTTPException(status_code=404, detail="attachment_missing")
    return FileResponse(path, filename=att.filename, media_type=att.mime)
