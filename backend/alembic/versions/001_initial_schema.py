"""initial schema

Revision ID: 001_initial_schema
Revises: 
Create Date: 2026-11-05 13:30:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Hospitals table
    op.create_table(
        "hospitals",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("address", sa.Text(), nullable=False),
        sa.Column("contact_number", sa.String(length=30), nullable=False),
    )
    op.create_index("ix_hospitals_id", "hospitals", ["id"])

    # 2. Doctors table
    op.create_table(
        "doctors",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("specialization", sa.String(length=100), nullable=False),
        sa.Column("availability", sa.Text(), nullable=False),
        sa.Column("consultation_fee", sa.Float(), nullable=False, server_default="50.0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.create_index("ix_doctors_id", "doctors", ["id"])
    op.create_index("ix_doctors_specialization", "doctors", ["specialization"])
    op.create_index("ix_doctors_is_active", "doctors", ["is_active"])

    # 3. Patients table
    op.create_table(
        "patients",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("phone_number", sa.String(length=30), nullable=False),
        sa.Column("email", sa.String(length=100), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_patients_id", "patients", ["id"])
    op.create_index("ix_patients_phone_number", "patients", ["phone_number"])

    # 4. Appointments table
    op.create_table(
        "appointments",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("patient_id", sa.Integer(), sa.ForeignKey("patients.id", ondelete="CASCADE"), nullable=False),
        sa.Column("doctor_id", sa.Integer(), sa.ForeignKey("doctors.id", ondelete="CASCADE"), nullable=False),
        sa.Column("appointment_date", sa.Date(), nullable=False),
        sa.Column("appointment_time", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="SCHEDULED"),
        sa.Column("booking_reference", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_appointments_id", "appointments", ["id"])
    op.create_index("ix_appointments_patient_id", "appointments", ["patient_id"])
    op.create_index("ix_appointments_doctor_id", "appointments", ["doctor_id"])
    op.create_index("ix_appointments_appointment_date", "appointments", ["appointment_date"])
    op.create_index("ix_appointments_status", "appointments", ["status"])
    op.create_index("ix_appointments_booking_reference", "appointments", ["booking_reference"], unique=True)
    op.create_index(
        "ix_appointments_doctor_date_time",
        "appointments",
        ["doctor_id", "appointment_date", "appointment_time"]
    )
    op.create_index(
        "ix_appointments_patient_date",
        "appointments",
        ["patient_id", "appointment_date"]
    )

    # 5. Call Sessions table
    op.create_table(
        "call_sessions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("caller_number", sa.String(length=30), nullable=False),
        sa.Column("call_direction", sa.String(length=20), nullable=False, server_default="INBOUND"),
        sa.Column("started_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("ended_at", sa.DateTime(), nullable=True),
        sa.Column("duration_seconds", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("transcript", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="COMPLETED"),
        sa.Column("estimated_cost", sa.Float(), nullable=False, server_default="0.0"),
    )
    op.create_index("ix_call_sessions_id", "call_sessions", ["id"])
    op.create_index("ix_call_sessions_caller_number", "call_sessions", ["caller_number"])
    op.create_index("ix_call_sessions_started_at", "call_sessions", ["started_at"])
    op.create_index("ix_call_sessions_status", "call_sessions", ["status"])

    # 6. Call Events table
    op.create_table(
        "call_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("call_session_id", sa.Integer(), sa.ForeignKey("call_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("event_type", sa.String(length=50), nullable=False),
        sa.Column("event_data", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_call_events_id", "call_events", ["id"])
    op.create_index("ix_call_events_call_session_id", "call_events", ["call_session_id"])
    op.create_index("ix_call_events_event_type", "call_events", ["event_type"])


def downgrade() -> None:
    op.drop_table("call_events")
    op.drop_table("call_sessions")
    op.drop_table("appointments")
    op.drop_table("patients")
    op.drop_table("doctors")
    op.drop_table("hospitals")
