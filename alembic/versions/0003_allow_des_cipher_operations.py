"""allow DES cipher operation history

Revision ID: 0003
Revises: 0002
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_OLD_CHECK = "cipher IN ('caesar', 'vigenere', 'playfair', 'affine', 'columnar', 'hill')"
_NEW_CHECK = "cipher IN ('caesar', 'vigenere', 'playfair', 'affine', 'columnar', 'hill', 'des')"


def upgrade() -> None:
    op.drop_constraint("ck_cipher_operations_cipher", "cipher_operations", type_="check")
    op.create_check_constraint("ck_cipher_operations_cipher", "cipher_operations", _NEW_CHECK)


def downgrade() -> None:
    op.drop_constraint("ck_cipher_operations_cipher", "cipher_operations", type_="check")
    op.create_check_constraint("ck_cipher_operations_cipher", "cipher_operations", _OLD_CHECK)
