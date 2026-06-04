"""add device_channels table and per-channel energy columns

Revision ID: 0004_device_channels_and_per_channel_energy
Revises: 0003_add_channel_columns
Create Date: 2026-06-04
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004_device_channels_and_per_channel_energy"
down_revision: str | None = "0003_add_channel_columns"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "device_channels",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("device_id", sa.Uuid(), nullable=False, index=True),
        sa.Column("channel_number", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(60), nullable=False),
        sa.Column("voltage", sa.Numeric(6, 1), nullable=False, server_default="110"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["device_id"], ["devices.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("device_id", "channel_number", name="uq_device_channel"),
    )

    op.add_column("telemetry", sa.Column("ch1_energy_kwh", sa.Numeric(12, 4), nullable=True))
    op.add_column("telemetry", sa.Column("ch2_energy_kwh", sa.Numeric(12, 4), nullable=True))
    op.add_column("telemetry", sa.Column("ch3_energy_kwh", sa.Numeric(12, 4), nullable=True))
    op.add_column("telemetry", sa.Column("ch4_energy_kwh", sa.Numeric(12, 4), nullable=True))


def downgrade() -> None:
    op.drop_column("telemetry", "ch4_energy_kwh")
    op.drop_column("telemetry", "ch3_energy_kwh")
    op.drop_column("telemetry", "ch2_energy_kwh")
    op.drop_column("telemetry", "ch1_energy_kwh")
    op.drop_table("device_channels")
