"""Create owner-scoped private history storage for SQLite."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "sqlite_0003"
down_revision: str | None = "sqlite_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_CIPHERS = "'caesar', 'vigenere', 'playfair', 'affine', 'columnar', 'hill', 'des', 'rsa', 'dh'"
_OPERATIONS = "'encrypt', 'decrypt', 'sign', 'verify'"


def upgrade() -> None:
    op.create_table(
        "private_history_records",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        # NULL is reserved for legacy/private rows that predate owner IDs.
        sa.Column("owner_id", sa.Text(), nullable=True),
        # Epoch microseconds are kept as a 64-bit integer for deterministic
        # ordering and portability between SQLite and PostgreSQL.
        sa.Column("created_at", sa.BigInteger(), nullable=False),
        sa.Column("cipher", sa.Text(), nullable=False),
        sa.Column("operation", sa.Text(), nullable=True),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("response_mode", sa.Text(), nullable=True),
        sa.Column("input_length", sa.Integer(), nullable=True),
        sa.Column("output_length", sa.Integer(), nullable=True),
        sa.Column("http_status", sa.Integer(), nullable=False),
        sa.Column("succeeded", sa.Integer(), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=False),
        sa.Column("content_bytes", sa.LargeBinary(), nullable=True),
        sa.Column("content_kind", sa.Text(), nullable=True),
        sa.Column("numeric_input_json", sa.Text(), nullable=True),
        sa.Column("signature_json", sa.Text(), nullable=True),
        sa.Column("public_key_json", sa.Text(), nullable=True),
        sa.Column("result_json", sa.Text(), nullable=True),
        sa.Column("validity", sa.Integer(), nullable=True),
        sa.Column("processing_state", sa.Text(), nullable=True),
        sa.Column("logical_size", sa.BigInteger(), nullable=False),
        sa.CheckConstraint(f"cipher IN ({_CIPHERS})", name="ck_private_history_cipher"),
        sa.CheckConstraint(
            f"operation IS NULL OR operation IN ({_OPERATIONS})",
            name="ck_private_history_operation",
        ),
        sa.CheckConstraint(
            "operation IS NULL OR operation IN ('encrypt', 'decrypt') "
            "OR (cipher = 'rsa' AND operation IN ('sign', 'verify'))",
            name="ck_private_history_rsa_operation",
        ),
        sa.CheckConstraint("source IN ('text', 'file')", name="ck_private_history_source"),
        sa.CheckConstraint(
            "response_mode IS NULL OR response_mode IN ('content', 'file')",
            name="ck_private_history_response_mode",
        ),
        sa.CheckConstraint(
            "owner_id IS NULL OR length(owner_id) > 0",
            name="ck_private_history_owner_nonempty",
        ),
        sa.CheckConstraint(
            "input_length IS NULL OR input_length >= 0",
            name="ck_private_history_input_length",
        ),
        sa.CheckConstraint(
            "output_length IS NULL OR output_length >= 0",
            name="ck_private_history_output_length",
        ),
        sa.CheckConstraint("succeeded IN (0, 1)", name="ck_private_history_succeeded"),
        sa.CheckConstraint("duration_ms >= 0", name="ck_private_history_duration_ms"),
        sa.CheckConstraint(
            "validity IS NULL OR validity IN (0, 1)",
            name="ck_private_history_validity",
        ),
        sa.CheckConstraint("logical_size >= 0", name="ck_private_history_logical_size"),
        sa.PrimaryKeyConstraint("id"),
        sqlite_autoincrement=True,
    )
    op.create_index(
        "ix_private_history_owner_created_at_id",
        "private_history_records",
        ["owner_id", sa.text("created_at DESC"), sa.text("id DESC")],
        unique=False,
    )
    op.create_index(
        "ix_private_history_created_at_id",
        "private_history_records",
        [sa.text("created_at ASC"), sa.text("id ASC")],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_private_history_owner_created_at_id",
        table_name="private_history_records",
    )
    op.drop_index(
        "ix_private_history_created_at_id",
        table_name="private_history_records",
    )
    op.drop_table("private_history_records")
