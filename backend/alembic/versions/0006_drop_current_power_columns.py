"""drop current and power columns from telemetry

Revision ID: 0006
Revises: 0005
Create Date: 2026-06-19

"""
from alembic import op
import sqlalchemy as sa


revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column("telemetry", "current")
    op.drop_column("telemetry", "power")


def downgrade() -> None:
    op.add_column("telemetry", sa.Column("current", sa.Numeric(10, 3), nullable=True))
    op.add_column("telemetry", sa.Column("power", sa.Numeric(10, 3), nullable=True))
