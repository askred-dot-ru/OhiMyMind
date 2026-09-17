"""initial envelope + mail schema

Revision ID: 001_initial
Revises:
Create Date: 2026-09-17
"""

from typing import Sequence, Union

from alembic import op

revision: str = "001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("CREATE EXTENSION IF NOT EXISTS citext")
    op.execute(
        """
        CREATE TABLE users (
            id UUID PRIMARY KEY,
            login CITEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL CHECK (role IN ('user', 'admin')),
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );

        CREATE TABLE knowledge_items (
            id UUID PRIMARY KEY,
            stream_kind TEXT NOT NULL CHECK (stream_kind IN ('mail', 'messenger', 'llm_session')),
            owner_user_id UUID NOT NULL REFERENCES users (id) ON DELETE CASCADE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            embedding vector(1536)
        );
        CREATE INDEX ix_knowledge_items_owner ON knowledge_items (owner_user_id);
        CREATE INDEX ix_knowledge_items_kind ON knowledge_items (stream_kind);

        CREATE TABLE topics (
            id UUID PRIMARY KEY,
            owner_user_id UUID NOT NULL REFERENCES users (id) ON DELETE CASCADE,
            name TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            UNIQUE (owner_user_id, name)
        );

        CREATE TABLE item_topics (
            item_id UUID NOT NULL REFERENCES knowledge_items (id) ON DELETE CASCADE,
            topic_id UUID NOT NULL REFERENCES topics (id) ON DELETE CASCADE,
            PRIMARY KEY (item_id, topic_id)
        );

        CREATE TABLE distribution_routes (
            id UUID PRIMARY KEY,
            item_id UUID NOT NULL REFERENCES knowledge_items (id) ON DELETE CASCADE,
            channel TEXT NOT NULL,
            payload_json JSONB,
            status TEXT NOT NULL DEFAULT 'stub',
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );

        CREATE TABLE mail_accounts (
            id UUID PRIMARY KEY,
            owner_user_id UUID NOT NULL REFERENCES users (id) ON DELETE CASCADE,
            provider TEXT NOT NULL CHECK (provider IN ('gmail', 'yandex')),
            email CITEXT NOT NULL,
            imap_host TEXT NOT NULL,
            imap_port INTEGER NOT NULL,
            smtp_host TEXT NOT NULL,
            smtp_port INTEGER NOT NULL,
            use_ssl BOOLEAN NOT NULL DEFAULT TRUE,
            unified BOOLEAN NOT NULL DEFAULT TRUE,
            is_default_compose BOOLEAN NOT NULL DEFAULT FALSE,
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            sync_state JSONB NOT NULL DEFAULT '{}'::jsonb,
            pending_empty_trash BOOLEAN NOT NULL DEFAULT FALSE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            UNIQUE (owner_user_id, email)
        );
        CREATE INDEX ix_mail_accounts_owner ON mail_accounts (owner_user_id);
        CREATE UNIQUE INDEX uq_mail_accounts_default_compose
            ON mail_accounts (owner_user_id)
            WHERE is_default_compose AND is_active;

        CREATE TABLE mail_account_secrets (
            account_id UUID PRIMARY KEY REFERENCES mail_accounts (id) ON DELETE CASCADE,
            blob BYTEA NOT NULL
        );

        CREATE TABLE mail_folder_maps (
            id UUID PRIMARY KEY,
            account_id UUID NOT NULL REFERENCES mail_accounts (id) ON DELETE CASCADE,
            canonical TEXT NOT NULL,
            imap_name TEXT NOT NULL,
            UNIQUE (account_id, canonical)
        );

        CREATE TABLE mail_threads (
            id UUID PRIMARY KEY,
            owner_user_id UUID NOT NULL REFERENCES users (id) ON DELETE CASCADE,
            subject_normalized TEXT NOT NULL DEFAULT '',
            participants TEXT NOT NULL DEFAULT '',
            last_message_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE INDEX ix_mail_threads_owner_last ON mail_threads (owner_user_id, last_message_at DESC);

        CREATE TABLE mail_messages (
            id UUID PRIMARY KEY,
            knowledge_item_id UUID NOT NULL UNIQUE REFERENCES knowledge_items (id) ON DELETE CASCADE,
            account_id UUID NOT NULL REFERENCES mail_accounts (id) ON DELETE CASCADE,
            thread_id UUID NOT NULL REFERENCES mail_threads (id) ON DELETE CASCADE,
            folder_canonical TEXT NOT NULL,
            uid BIGINT,
            message_id_header TEXT NOT NULL DEFAULT '',
            in_reply_to TEXT NOT NULL DEFAULT '',
            references_header TEXT NOT NULL DEFAULT '',
            subject TEXT NOT NULL DEFAULT '',
            from_addr TEXT NOT NULL DEFAULT '',
            to_json JSONB NOT NULL DEFAULT '[]'::jsonb,
            cc_json JSONB NOT NULL DEFAULT '[]'::jsonb,
            body_text TEXT NOT NULL DEFAULT '',
            body_html TEXT NOT NULL DEFAULT '',
            flags TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
            sent_at TIMESTAMPTZ,
            pending_imap TEXT,
            sync_error TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            UNIQUE (account_id, folder_canonical, uid)
        );
        CREATE INDEX ix_mail_messages_thread ON mail_messages (thread_id);
        CREATE INDEX ix_mail_messages_folder ON mail_messages (account_id, folder_canonical);
        CREATE INDEX ix_mail_messages_msgid ON mail_messages (account_id, message_id_header);

        ALTER TABLE mail_messages
            ADD COLUMN fts tsvector
            GENERATED ALWAYS AS (
                to_tsvector(
                    'simple',
                    coalesce(subject, '') || ' ' || coalesce(body_text, '')
                )
            ) STORED;
        CREATE INDEX ix_mail_messages_fts ON mail_messages USING GIN (fts);

        CREATE TABLE mail_attachments (
            id UUID PRIMARY KEY,
            message_id UUID NOT NULL REFERENCES mail_messages (id) ON DELETE CASCADE,
            filename TEXT NOT NULL,
            mime TEXT NOT NULL DEFAULT 'application/octet-stream',
            size_bytes BIGINT NOT NULL,
            sha256 TEXT NOT NULL,
            storage_path TEXT NOT NULL
        );
        CREATE INDEX ix_mail_attachments_message ON mail_attachments (message_id);

        CREATE TABLE mail_outbox (
            id UUID PRIMARY KEY,
            account_id UUID NOT NULL REFERENCES mail_accounts (id) ON DELETE CASCADE,
            owner_user_id UUID NOT NULL REFERENCES users (id) ON DELETE CASCADE,
            to_json JSONB NOT NULL,
            cc_json JSONB NOT NULL DEFAULT '[]'::jsonb,
            subject TEXT NOT NULL DEFAULT '',
            body_html TEXT NOT NULL DEFAULT '',
            in_reply_to_header TEXT NOT NULL DEFAULT '',
            references_header TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'sent', 'failed')),
            error_text TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            sent_at TIMESTAMPTZ
        );
        CREATE INDEX ix_mail_outbox_pending ON mail_outbox (status, created_at)
            WHERE status = 'pending';
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DROP TABLE IF EXISTS mail_outbox;
        DROP TABLE IF EXISTS mail_attachments;
        DROP TABLE IF EXISTS mail_messages;
        DROP TABLE IF EXISTS mail_threads;
        DROP TABLE IF EXISTS mail_folder_maps;
        DROP TABLE IF EXISTS mail_account_secrets;
        DROP TABLE IF EXISTS mail_accounts;
        DROP TABLE IF EXISTS distribution_routes;
        DROP TABLE IF EXISTS item_topics;
        DROP TABLE IF EXISTS topics;
        DROP TABLE IF EXISTS knowledge_items;
        DROP TABLE IF EXISTS users;
        """
    )
