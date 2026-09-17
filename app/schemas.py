from __future__ import annotations

import uuid
from typing import Any

from pydantic import BaseModel, EmailStr, Field


class RegisterIn(BaseModel):
    login: str = Field(min_length=1, max_length=128)
    password: str = Field(min_length=8, max_length=256)


class LoginIn(BaseModel):
    login: str
    password: str


class UserOut(BaseModel):
    login: str
    role: str


class RegisterOut(BaseModel):
    id: uuid.UUID
    login: str
    role: str


class YandexAccountIn(BaseModel):
    provider: str
    email: EmailStr
    app_password: str = Field(min_length=1)
    imap_host: str | None = None
    imap_port: int | None = None
    smtp_host: str | None = None
    smtp_port: int | None = None


class AccountPatchIn(BaseModel):
    unified: bool | None = None
    is_default_compose: bool | None = None


class AccountOut(BaseModel):
    id: uuid.UUID
    provider: str
    email: str
    unified: bool
    is_default_compose: bool
    imap_host: str
    smtp_host: str


class FolderNode(BaseModel):
    id: str
    canonical: str
    name: str
    account_id: uuid.UUID | None = None


class FolderTree(BaseModel):
    kind: str
    label: str | None
    folders: list[FolderNode]


class ThreadHead(BaseModel):
    id: uuid.UUID
    subject: str
    from_addr: str
    snippet: str
    last_at: str | None
    unread: bool
    flagged: bool
    account_id: uuid.UUID
    folder_canonical: str
    provider: str = ""


class AttachmentMeta(BaseModel):
    id: uuid.UUID
    filename: str
    mime: str
    size_bytes: int
    content_id: str = ""


class MessageOut(BaseModel):
    id: uuid.UUID
    account_id: uuid.UUID
    provider: str = ""
    folder_canonical: str
    subject: str
    from_addr: str
    to: list[Any]
    cc: list[Any]
    sent_at: str | None
    body_text: str
    body_html: str
    flags: list[str]
    attachments: list[AttachmentMeta]


class ThreadOut(BaseModel):
    id: uuid.UUID
    messages: list[MessageOut]


class ComposeIn(BaseModel):
    account_id: uuid.UUID
    to: list[str]
    cc: list[str] = Field(default_factory=list)
    subject: str = ""
    body_html: str = ""
    in_reply_to: uuid.UUID | None = None
    forward_of: uuid.UUID | None = None
    draft: bool = False


class ThreadFlagsIn(BaseModel):
    seen: bool | None = None
    flagged: bool | None = None
    message_id: uuid.UUID | None = None
