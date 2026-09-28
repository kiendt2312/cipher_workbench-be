"""create cipher_operations

Revision ID: 0001
Revises: none
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "cipher_operations",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("cipher", sa.Text(), nullable=False),
        sa.Column("operation", sa.Text(), nullable=True),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("response_mode", sa.Text(), nullable=True),
        sa.Column("input_length", sa.Integer(), nullable=True),
        sa.Column("output_length", sa.Integer(), nullable=True),
        sa.Column("http_status", sa.SmallInteger(), nullable=False),
        sa.Column("succeeded", sa.Boolean(), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "cipher IN ('caesar', 'vigenere', 'playfair', 'affine', 'columnar')",
            name="ck_cipher_operations_cipher",
        ),
        sa.CheckConstraint(
            "operation IN ('encrypt', 'decrypt')", name="ck_cipher_operations_operation"
        ),
        sa.CheckConstraint(
            "response_mode IN ('content', 'file')", name="ck_cipher_operations_response_mode"
        ),
        sa.CheckConstraint("source IN ('text', 'file')", name="ck_cipher_operations_source"),
        sa.CheckConstraint("duration_ms >= 0", name="ck_cipher_operations_duration_ms"),
        sa.CheckConstraint("input_length >= 0", name="ck_cipher_operations_input_length"),
        sa.CheckConstraint("output_length >= 0", name="ck_cipher_operations_output_length"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_cipher_operations_cipher_created_at",
        "cipher_operations",
        ["cipher", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_cipher_operations_created_at_id",
        "cipher_operations",
        ["created_at", "id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_cipher_operations_created_at_id", table_name="cipher_operations")
    op.drop_index("ix_cipher_operations_cipher_created_at", table_name="cipher_operations")
    op.drop_table("cipher_operations")
