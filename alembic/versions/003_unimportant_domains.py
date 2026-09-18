"""users.unimportant_domains — inbox section 2

Revision ID: 003_unimportant_domains
Revises: 002_attachment_cid
Create Date: 2026-09-18
"""

from typing import Sequence, Union

from alembic import op

revision: str = "003_unimportant_domains"
down_revision: Union[str, None] = "002_attachment_cid"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS unimportant_domains JSONB NOT NULL DEFAULT '[]'::jsonb")


def downgrade() -> None:
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS unimportant_domains")
