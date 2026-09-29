"""allow Hill cipher operation history

Revision ID: 0002
Revises: 0001
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_OLD_CHECK = "cipher IN ('caesar', 'vigenere', 'playfair', 'affine', 'columnar')"
_NEW_CHECK = "cipher IN ('caesar', 'vigenere', 'playfair', 'affine', 'columnar', 'hill')"


def upgrade() -> None:
    op.drop_constraint("ck_cipher_operations_cipher", "cipher_operations", type_="check")
    op.create_check_constraint("ck_cipher_operations_cipher", "cipher_operations", _NEW_CHECK)


def downgrade() -> None:
    op.drop_constraint("ck_cipher_operations_cipher", "cipher_operations", type_="check")
    op.create_check_constraint("ck_cipher_operations_cipher", "cipher_operations", _OLD_CHECK)
