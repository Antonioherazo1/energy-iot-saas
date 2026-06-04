"""add ch1-ch4 channel columns to telemetry

Revision ID: 0003_add_channel_columns
Revises: 0002_add_device_credentials
Create Date: 2026-06-03
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003_add_channel_columns"
down_revision: str | None = "0002_add_device_credentials"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("telemetry", sa.Column("ch1", sa.Numeric(10, 3), nullable=True))
    op.add_column("telemetry", sa.Column("ch2", sa.Numeric(10, 3), nullable=True))
    op.add_column("telemetry", sa.Column("ch3", sa.Numeric(10, 3), nullable=True))
    op.add_column("telemetry", sa.Column("ch4", sa.Numeric(10, 3), nullable=True))


def downgrade() -> None:
    op.drop_column("telemetry", "ch4")
    op.drop_column("telemetry", "ch3")
    op.drop_column("telemetry", "ch2")
    op.drop_column("telemetry", "ch1")
