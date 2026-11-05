"""add active slot unique constraints

Revision ID: 002_add_concurrency_constraints
Revises: 001_initial_schema
Create Date: 2026-11-05 14:10:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "002_add_concurrency_constraints"
down_revision: Union[str, None] = "001_initial_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Partial Unique Index on active doctor slots
    op.create_index(
        "uq_active_doctor_slot",
        "appointments",
        ["doctor_id", "appointment_date", "appointment_time"],
        unique=True,
        postgresql_where=sa.text("status IN ('SCHEDULED', 'RESCHEDULED')"),
        sqlite_where=sa.text("status IN ('SCHEDULED', 'RESCHEDULED')"),
    )

    # 2. Partial Unique Index on active patient overlapping bookings
    op.create_index(
        "uq_active_patient_slot",
        "appointments",
        ["patient_id", "appointment_date", "appointment_time"],
        unique=True,
        postgresql_where=sa.text("status IN ('SCHEDULED', 'RESCHEDULED')"),
        sqlite_where=sa.text("status IN ('SCHEDULED', 'RESCHEDULED')"),
    )


def downgrade() -> None:
    op.drop_index("uq_active_patient_slot", table_name="appointments")
    op.drop_index("uq_active_doctor_slot", table_name="appointments")

