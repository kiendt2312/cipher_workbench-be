"""allow RSA cipher operation history

Revision ID: 0004
Revises: 0003
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_OLD_CHECK = "cipher IN ('caesar', 'vigenere', 'playfair', 'affine', 'columnar', 'hill', 'des')"
_NEW_CHECK = (
    "cipher IN ('caesar', 'vigenere', 'playfair', 'affine', 'columnar', 'hill', 'des', 'rsa')"
)


def upgrade() -> None:
    op.drop_constraint("ck_cipher_operations_cipher", "cipher_operations", type_="check")
    op.create_check_constraint("ck_cipher_operations_cipher", "cipher_operations", _NEW_CHECK)


def downgrade() -> None:
    op.drop_constraint("ck_cipher_operations_cipher", "cipher_operations", type_="check")
    op.create_check_constraint("ck_cipher_operations_cipher", "cipher_operations", _OLD_CHECK)
