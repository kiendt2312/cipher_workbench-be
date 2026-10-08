"""Add Diffie-Hellman operation history support to SQLite."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "sqlite_0002"
down_revision: str | None = "sqlite_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_BASE_CIPHERS = "'caesar', 'vigenere', 'playfair', 'affine', 'columnar', 'hill', 'des', 'rsa'"
_DH_CIPHERS = f"{_BASE_CIPHERS}, 'dh'"


def _create_cipher_operations(table_name: str, cipher_values: str) -> None:
    op.create_table(
        table_name,
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=True),
        sa.Column("created_at", sa.Integer(), nullable=False),
        sa.Column("cipher", sa.Text(), nullable=False),
        sa.Column("operation", sa.Text(), nullable=True),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("response_mode", sa.Text(), nullable=True),
        sa.Column("input_length", sa.Integer(), nullable=True),
        sa.Column("output_length", sa.Integer(), nullable=True),
        sa.Column("http_status", sa.Integer(), nullable=False),
        sa.Column("succeeded", sa.Integer(), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            f"cipher IN ({cipher_values})",
            name="ck_cipher_operations_cipher",
        ),
        sa.CheckConstraint(
            "operation IN ('encrypt', 'decrypt')", name="ck_cipher_operations_operation"
        ),
        sa.CheckConstraint("source IN ('text', 'file')", name="ck_cipher_operations_source"),
        sa.CheckConstraint(
            "response_mode IN ('content', 'file')", name="ck_cipher_operations_response_mode"
        ),
        sa.CheckConstraint("input_length >= 0", name="ck_cipher_operations_input_length"),
        sa.CheckConstraint("output_length >= 0", name="ck_cipher_operations_output_length"),
        sa.CheckConstraint("succeeded IN (0, 1)", name="ck_cipher_operations_succeeded"),
        sa.CheckConstraint("duration_ms >= 0", name="ck_cipher_operations_duration_ms"),
        sa.CheckConstraint("id > 0", name="ck_cipher_operations_id_positive"),
        sa.PrimaryKeyConstraint("id"),
        sqlite_autoincrement=True,
    )


def _create_indexes() -> None:
    op.create_index(
        "ix_cipher_operations_created_at_id",
        "cipher_operations",
        [sa.text("created_at DESC"), sa.text("id DESC")],
        unique=False,
    )
    op.create_index(
        "ix_cipher_operations_cipher_created_at",
        "cipher_operations",
        ["cipher", sa.text("created_at DESC"), sa.text("id DESC")],
        unique=False,
    )


def _rebuild(cipher_values: str) -> None:
    bind = op.get_bind()
    sequence_row = bind.execute(
        sa.text("SELECT seq FROM sqlite_sequence WHERE name = 'cipher_operations'")
    ).first()
    sequence = None if sequence_row is None else sequence_row[0]

    op.drop_index("ix_cipher_operations_created_at_id", table_name="cipher_operations")
    op.drop_index("ix_cipher_operations_cipher_created_at", table_name="cipher_operations")
    op.rename_table("cipher_operations", "cipher_operations_sqlite_rebuild_old")
    _create_cipher_operations("cipher_operations_sqlite_rebuild_new", cipher_values)
    bind.execute(
        sa.text(
            "INSERT INTO cipher_operations_sqlite_rebuild_new "
            "(id, created_at, cipher, operation, source, response_mode, input_length, "
            "output_length, http_status, succeeded, duration_ms) "
            "SELECT id, created_at, cipher, operation, source, response_mode, input_length, "
            "output_length, http_status, succeeded, duration_ms "
            "FROM cipher_operations_sqlite_rebuild_old"
        )
    )
    op.drop_table("cipher_operations_sqlite_rebuild_old")
    op.rename_table("cipher_operations_sqlite_rebuild_new", "cipher_operations")
    _create_indexes()

    bind.execute(sa.text("DELETE FROM sqlite_sequence WHERE name = 'cipher_operations'"))
    if sequence is not None:
        bind.execute(
            sa.text("INSERT INTO sqlite_sequence(name, seq) VALUES ('cipher_operations', :seq)"),
            {"seq": sequence},
        )


def upgrade() -> None:
    _rebuild(_DH_CIPHERS)


def downgrade() -> None:
    bind = op.get_bind()
    dh_row = bind.execute(
        sa.text("SELECT 1 FROM cipher_operations WHERE cipher = 'dh' LIMIT 1")
    ).first()
    if dh_row is not None:
        raise RuntimeError("cannot downgrade SQLite history while DH rows exist")
    _rebuild(_BASE_CIPHERS)
