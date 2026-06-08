"""add device credentials

Revision ID: 0002_add_device_credentials
Revises: 0001_initial_schema
Create Date: 2026-06-01
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_add_device_credentials"
down_revision: str | None = "0001_initial_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Column already exists in 0001_initial_schema
    pass


def downgrade() -> None:
    # Column already exists in 0001_initial_schema
    pass

