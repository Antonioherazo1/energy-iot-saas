"""create raw_telemetry table

Revision ID: 0007
Revises: 0006
Create Date: 2026-06-23

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "raw_telemetry",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, default=sa.text("gen_random_uuid()")),
        sa.Column("device_id", UUID(as_uuid=True), sa.ForeignKey("devices.id", ondelete="CASCADE"), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ch1", sa.Float, nullable=True),
        sa.Column("ch2", sa.Float, nullable=True),
        sa.Column("ch3", sa.Float, nullable=True),
        sa.Column("ch4", sa.Float, nullable=True),
        sa.Column("energy_kwh", sa.Numeric(12, 4), nullable=True),
        sa.Column("voltage", sa.Float, nullable=True),
        sa.Column("frequency", sa.Float, nullable=True),
        sa.Column("power_factor", sa.Float, nullable=True),
        sa.Column("ch1_energy_kwh", sa.Numeric(12, 4), nullable=True),
        sa.Column("ch2_energy_kwh", sa.Numeric(12, 4), nullable=True),
        sa.Column("ch3_energy_kwh", sa.Numeric(12, 4), nullable=True),
        sa.Column("ch4_energy_kwh", sa.Numeric(12, 4), nullable=True),
    )
    op.create_index("ix_raw_telemetry_device_recorded_at", "raw_telemetry", ["device_id", "recorded_at"])


def downgrade() -> None:
    op.drop_index("ix_raw_telemetry_device_recorded_at")
    op.drop_table("raw_telemetry")
