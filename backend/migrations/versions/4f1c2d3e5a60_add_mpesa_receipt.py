"""add mpesa_receipt to payments

Revision ID: 4f1c2d3e5a60
Revises: 2ac145176d01
"""
from alembic import op
import sqlalchemy as sa

revision: str = "4f1c2d3e5a60"
down_revision: Union[str, None] = "2ac145176d01"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    op.add_column(
        "payments",
        sa.Column("mpesa_receipt", sa.String(length=100), nullable=True),
    )
    op.create_index(
        "ix_payments_mpesa_receipt", "payments", ["mpesa_receipt"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_payments_mpesa_receipt", table_name="payments")
    op.drop_column("payments", "mpesa_receipt")
