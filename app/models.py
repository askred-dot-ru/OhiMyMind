from __future__ import annotations

import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Computed,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, BYTEA, CITEXT, JSONB, TSVECTOR, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    __table_args__ = (CheckConstraint("role IN ('user', 'admin')", name="ck_users_role"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    login: Mapped[str] = mapped_column(CITEXT, unique=True)
    password_hash: Mapped[str] = mapped_column(Text)
    role: Mapped[str] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))


class KnowledgeItem(Base):
    __tablename__ = "knowledge_items"
    __table_args__ = (
        CheckConstraint(
            "stream_kind IN ('mail', 'messenger', 'llm_session')",
            name="ck_knowledge_items_kind",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    stream_kind: Mapped[str] = mapped_column(Text)
    owner_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))
    embedding: Mapped[list[float] | None] = mapped_column(Vector(1536), nullable=True)

    mail_message: Mapped[MailMessage | None] = relationship(back_populates="knowledge_item")


class Topic(Base):
    __tablename__ = "topics"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))


class ItemTopic(Base):
    __tablename__ = "item_topics"

    item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("knowledge_items.id", ondelete="CASCADE"), primary_key=True
    )
    topic_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("topics.id", ondelete="CASCADE"), primary_key=True
    )


class DistributionRoute(Base):
    __tablename__ = "distribution_routes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    item_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("knowledge_items.id", ondelete="CASCADE"))
    channel: Mapped[str] = mapped_column(Text)
    payload_json: Mapped[dict | None] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(Text, default="stub")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))


class MailAccount(Base):
    __tablename__ = "mail_accounts"
    __table_args__ = (
        CheckConstraint("provider IN ('gmail', 'yandex')", name="ck_mail_accounts_provider"),
        UniqueConstraint("owner_user_id", "email", name="uq_mail_accounts_owner_email"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"))
    provider: Mapped[str] = mapped_column(Text)
    email: Mapped[str] = mapped_column(CITEXT)
    imap_host: Mapped[str] = mapped_column(Text)
    imap_port: Mapped[int]
    smtp_host: Mapped[str] = mapped_column(Text)
    smtp_port: Mapped[int]
    use_ssl: Mapped[bool] = mapped_column(Boolean, default=True)
    unified: Mapped[bool] = mapped_column(Boolean, default=True)
    is_default_compose: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    sync_state: Mapped[dict] = mapped_column(JSONB, default=dict)
    pending_empty_trash: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))

    secret: Mapped[MailAccountSecret | None] = relationship(back_populates="account", uselist=False)
    folder_maps: Mapped[list[MailFolderMap]] = relationship(back_populates="account")


class MailAccountSecret(Base):
    __tablename__ = "mail_account_secrets"

    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("mail_accounts.id", ondelete="CASCADE"), primary_key=True
    )
    blob: Mapped[bytes] = mapped_column(BYTEA)

    account: Mapped[MailAccount] = relationship(back_populates="secret")


class MailFolderMap(Base):
    __tablename__ = "mail_folder_maps"
    __table_args__ = (UniqueConstraint("account_id", "canonical", name="uq_mail_folder_maps_canonical"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    account_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("mail_accounts.id", ondelete="CASCADE"))
    canonical: Mapped[str] = mapped_column(Text)
    imap_name: Mapped[str] = mapped_column(Text)

    account: Mapped[MailAccount] = relationship(back_populates="folder_maps")


class MailThread(Base):
    __tablename__ = "mail_threads"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"))
    subject_normalized: Mapped[str] = mapped_column(Text, default="")
    participants: Mapped[str] = mapped_column(Text, default="")
    last_message_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))

    messages: Mapped[list[MailMessage]] = relationship(back_populates="thread")


class MailMessage(Base):
    __tablename__ = "mail_messages"
    __table_args__ = (
        UniqueConstraint("account_id", "folder_canonical", "uid", name="uq_mail_messages_uid"),
        Index("ix_mail_messages_thread", "thread_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    knowledge_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("knowledge_items.id", ondelete="CASCADE"), unique=True
    )
    account_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("mail_accounts.id", ondelete="CASCADE"))
    thread_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("mail_threads.id", ondelete="CASCADE"))
    folder_canonical: Mapped[str] = mapped_column(Text)
    uid: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    message_id_header: Mapped[str] = mapped_column(Text, default="")
    in_reply_to: Mapped[str] = mapped_column(Text, default="")
    references_header: Mapped[str] = mapped_column(Text, default="")
    subject: Mapped[str] = mapped_column(Text, default="")
    from_addr: Mapped[str] = mapped_column(Text, default="")
    to_json: Mapped[list] = mapped_column(JSONB, default=list)
    cc_json: Mapped[list] = mapped_column(JSONB, default=list)
    body_text: Mapped[str] = mapped_column(Text, default="")
    body_html: Mapped[str] = mapped_column(Text, default="")
    flags: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    pending_imap: Mapped[str | None] = mapped_column(Text, nullable=True)
    sync_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))
    fts: Mapped[str | None] = mapped_column(
        TSVECTOR,
        Computed(
            "to_tsvector('simple', coalesce(subject, '') || ' ' || coalesce(body_text, ''))",
            persisted=True,
        ),
    )

    knowledge_item: Mapped[KnowledgeItem] = relationship(back_populates="mail_message")
    thread: Mapped[MailThread] = relationship(back_populates="messages")
    attachments: Mapped[list[MailAttachment]] = relationship(back_populates="message")
    account: Mapped[MailAccount] = relationship()


class MailAttachment(Base):
    __tablename__ = "mail_attachments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    message_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("mail_messages.id", ondelete="CASCADE")
    )
    filename: Mapped[str] = mapped_column(Text)
    mime: Mapped[str] = mapped_column(Text, default="application/octet-stream")
    size_bytes: Mapped[int] = mapped_column(BigInteger)
    sha256: Mapped[str] = mapped_column(Text)
    storage_path: Mapped[str] = mapped_column(Text)
    content_id: Mapped[str] = mapped_column(Text, default="")

    message: Mapped[MailMessage] = relationship(back_populates="attachments")


class MailOutbox(Base):
    __tablename__ = "mail_outbox"
    __table_args__ = (
        CheckConstraint("status IN ('pending', 'sent', 'failed')", name="ck_mail_outbox_status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    account_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("mail_accounts.id", ondelete="CASCADE"))
    owner_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"))
    to_json: Mapped[list] = mapped_column(JSONB)
    cc_json: Mapped[list] = mapped_column(JSONB, default=list)
    subject: Mapped[str] = mapped_column(Text, default="")
    body_html: Mapped[str] = mapped_column(Text, default="")
    in_reply_to_header: Mapped[str] = mapped_column(Text, default="")
    references_header: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(Text, default="pending")
    error_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
