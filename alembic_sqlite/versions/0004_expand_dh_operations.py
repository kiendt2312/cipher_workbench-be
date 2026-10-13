"""Allow the standalone Diffie-Hellman operations in both SQLite history tables."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "sqlite_0004"
down_revision: str | None = "sqlite_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_CIPHERS = "'caesar', 'vigenere', 'playfair', 'affine', 'columnar', 'hill', 'des', 'rsa', 'dh'"
_DH_OPERATIONS = (
    "'validate_params', 'generate_params', 'generate_keypair', 'derive_shared_secret', 'exchange'"
)
_TRANSFORM_OPERATIONS = "'encrypt', 'decrypt'"
_RSA_OPERATIONS = "'sign', 'verify'"
_CIPHER_COLUMNS = (
    "id, created_at, cipher, operation, source, response_mode, input_length, "
    "output_length, http_status, succeeded, duration_ms"
)
_PRIVATE_COLUMNS = (
    "id, owner_id, created_at, cipher, operation, source, response_mode, input_length, "
    "output_length, http_status, succeeded, duration_ms, content_bytes, content_kind, "
    "numeric_input_json, signature_json, public_key_json, result_json, validity, "
    "processing_state, logical_size"
)


def _create_cipher_operations(table_name: str, *, include_dh_operations: bool) -> None:
    operation_constraint = (
        f"operation IS NULL OR operation IN ({_TRANSFORM_OPERATIONS}) "
        f"OR (cipher = 'dh' AND operation IN ({_DH_OPERATIONS}))"
        if include_dh_operations
        else f"operation IS NULL OR operation IN ({_TRANSFORM_OPERATIONS})"
    )
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
        sa.CheckConstraint(f"cipher IN ({_CIPHERS})", name="ck_cipher_operations_cipher"),
        sa.CheckConstraint(operation_constraint, name="ck_cipher_operations_operation"),
        sa.CheckConstraint("source IN ('text', 'file')", name="ck_cipher_operations_source"),
        sa.CheckConstraint(
            "response_mode IN ('content', 'file')",
            name="ck_cipher_operations_response_mode",
        ),
        sa.CheckConstraint("input_length >= 0", name="ck_cipher_operations_input_length"),
        sa.CheckConstraint("output_length >= 0", name="ck_cipher_operations_output_length"),
        sa.CheckConstraint("succeeded IN (0, 1)", name="ck_cipher_operations_succeeded"),
        sa.CheckConstraint("duration_ms >= 0", name="ck_cipher_operations_duration_ms"),
        sa.CheckConstraint("id > 0", name="ck_cipher_operations_id_positive"),
        sa.PrimaryKeyConstraint("id"),
        sqlite_autoincrement=True,
    )


def _create_private_history_records(table_name: str, *, include_dh_operations: bool) -> None:
    allowed_operations = (
        f"{_TRANSFORM_OPERATIONS}, {_DH_OPERATIONS}, {_RSA_OPERATIONS}"
        if include_dh_operations
        else f"{_TRANSFORM_OPERATIONS}, {_RSA_OPERATIONS}"
    )
    operation_constraint = (
        f"operation IS NULL OR operation IN ({_TRANSFORM_OPERATIONS}) "
        f"OR (cipher = 'dh' AND operation IN ({_DH_OPERATIONS})) "
        f"OR (cipher = 'rsa' AND operation IN ({_RSA_OPERATIONS}))"
        if include_dh_operations
        else f"operation IS NULL OR operation IN ({_TRANSFORM_OPERATIONS}) "
        f"OR (cipher = 'rsa' AND operation IN ({_RSA_OPERATIONS}))"
    )
    op.create_table(
        table_name,
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("owner_id", sa.Text(), nullable=True),
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
            f"operation IS NULL OR operation IN ({allowed_operations})",
            name="ck_private_history_operation",
        ),
        sa.CheckConstraint(operation_constraint, name="ck_private_history_rsa_operation"),
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


def _sequence(bind: sa.Connection, table_name: str) -> int | None:
    row = bind.execute(
        sa.text("SELECT seq FROM sqlite_sequence WHERE name = :table_name"),
        {"table_name": table_name},
    ).first()
    return None if row is None else row[0]


def _restore_sequence(bind: sa.Connection, table_name: str, sequence: int | None) -> None:
    bind.execute(
        sa.text("DELETE FROM sqlite_sequence WHERE name = :table_name"),
        {"table_name": table_name},
    )
    if sequence is not None:
        bind.execute(
            sa.text("INSERT INTO sqlite_sequence(name, seq) VALUES (:table_name, :sequence)"),
            {"table_name": table_name, "sequence": sequence},
        )


def _indexes(bind: sa.Connection, table_name: str) -> list[tuple[str, str]]:
    rows = bind.execute(
        sa.text(
            "SELECT name, sql FROM sqlite_master "
            "WHERE type = 'index' AND tbl_name = :table_name AND sql IS NOT NULL "
            "ORDER BY name"
        ),
        {"table_name": table_name},
    )
    return [(str(row[0]), str(row[1])) for row in rows]


def _rebuild_table(
    table_name: str,
    columns: str,
    create_table,
) -> None:
    bind = op.get_bind()
    sequence = _sequence(bind, table_name)
    indexes = _indexes(bind, table_name)
    for index_name, _sql in indexes:
        op.drop_index(index_name, table_name=table_name)

    old_name = f"{table_name}_sqlite_rebuild_old"
    new_name = f"{table_name}_sqlite_rebuild_new"
    op.rename_table(table_name, old_name)
    create_table(new_name)
    bind.execute(sa.text(f"INSERT INTO {new_name} ({columns}) SELECT {columns} FROM {old_name}"))
    op.drop_table(old_name)
    op.rename_table(new_name, table_name)
    for _index_name, index_sql in indexes:
        bind.exec_driver_sql(index_sql)
    _restore_sequence(bind, table_name, sequence)


def _rebuild_tables(*, include_dh_operations: bool) -> None:
    _rebuild_table(
        "cipher_operations",
        _CIPHER_COLUMNS,
        lambda table_name: _create_cipher_operations(
            table_name, include_dh_operations=include_dh_operations
        ),
    )
    _rebuild_table(
        "private_history_records",
        _PRIVATE_COLUMNS,
        lambda table_name: _create_private_history_records(
            table_name, include_dh_operations=include_dh_operations
        ),
    )


def upgrade() -> None:
    _rebuild_tables(include_dh_operations=True)


def downgrade() -> None:
    bind = op.get_bind()
    dh_operation = f"operation IN ({_DH_OPERATIONS})"
    existing = bind.execute(
        sa.text(f"SELECT 1 FROM cipher_operations WHERE {dh_operation} LIMIT 1")
    ).first()
    if existing is None:
        existing = bind.execute(
            sa.text(f"SELECT 1 FROM private_history_records WHERE {dh_operation} LIMIT 1")
        ).first()
    if existing is not None:
        raise RuntimeError("cannot downgrade SQLite history while DH operation rows exist")
    _rebuild_tables(include_dh_operations=False)
