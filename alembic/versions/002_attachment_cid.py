"""mail_attachments.content_id for cid: inline images

Revision ID: 002_attachment_cid
Revises: 001_initial
Create Date: 2026-09-17
"""

from typing import Sequence, Union

from alembic import op

revision: str = "002_attachment_cid"
down_revision: Union[str, None] = "001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE mail_attachments ADD COLUMN IF NOT EXISTS content_id TEXT NOT NULL DEFAULT ''")


def downgrade() -> None:
    op.execute("ALTER TABLE mail_attachments DROP COLUMN IF EXISTS content_id")
