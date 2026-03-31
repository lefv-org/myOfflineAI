"""add watched_directory table

Revision ID: f27ac8ab2bb6
Revises: b2c3d4e5f6a7
Create Date: 2026-03-31 15:32:20.428802

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from open_webui.migrations.util import get_existing_tables

# revision identifiers, used by Alembic.
revision: str = 'f27ac8ab2bb6'
down_revision: Union[str, None] = 'b2c3d4e5f6a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    existing_tables = set(get_existing_tables())

    if "watched_directory" not in existing_tables:
        op.create_table(
            "watched_directory",
            sa.Column("id", sa.Text(), nullable=False),
            sa.Column("user_id", sa.Text(), nullable=False),
            sa.Column("path", sa.Text(), nullable=False),
            sa.Column("name", sa.Text(), nullable=False),
            sa.Column("knowledge_id", sa.Text(), nullable=True),
            sa.Column("extensions", sa.Text(), nullable=True),
            sa.Column("exclude_patterns", sa.Text(), nullable=True),
            sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("last_scan_at", sa.BigInteger(), nullable=True),
            sa.Column("created_at", sa.BigInteger(), nullable=False),
            sa.Column("updated_at", sa.BigInteger(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("path"),
        )


def downgrade() -> None:
    op.drop_table("watched_directory")
