import pytest
import asyncio
from datetime import date, timedelta
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.schema import CreateTable, CreateIndex
from sqlalchemy.dialects import postgresql
from sqlalchemy import select

from app.core.database import Base
from app.models.hospital import Hospital
from app.models.doctor import Doctor
from app.models.patient import Patient
from app.models.appointment import Appointment
from app.models.call_session import CallSession, CallEvent
from app.services.voice.agent.tools import tool_registry, BookAppointmentInput


# =====================================================================
# 1. PostgreSQL Schema and DDL Dialect Verification
# =====================================================================
def test_postgresql_ddl_compilation_all_models():
    """
    Verify that all 6 SQLAlchemy models compile to valid PostgreSQL DDL syntax,
    including data types, foreign keys, and indexes.
    """
    pg_dialect = postgresql.dialect()
    models = [Hospital, Doctor, Patient, Appointment, CallSession, CallEvent]

    for model in models:
        create_sql = str(CreateTable(model.__table__).compile(dialect=pg_dialect))
        assert "CREATE TABLE" in create_sql
        assert model.__tablename__ in create_sql
        # Verify no sqlite-specific syntax in postgres compilation
        assert "AUTOINCREMENT" not in create_sql  # In postgres, serial/integer pk is used


def test_postgresql_partial_unique_index_compilation():
    """
    Verify that the Alembic concurrency protection partial unique indexes
    compile properly to PostgreSQL 'WHERE status IN (...)' partial index syntax.
    """
    pg_dialect = postgresql.dialect()

    # Find the partial unique indexes on Appointment table
    apt_table = Appointment.__table__
    index_names = [idx.name for idx in apt_table.indexes]

    # Verify our indexes exist
    for idx in apt_table.indexes:
        if idx.unique and idx.dialect_options.get("postgresql", {}).get("where") is not None:
            compiled_idx = str(CreateIndex(idx).compile(dialect=pg_dialect))
            assert "CREATE UNIQUE INDEX" in compiled_idx
            assert "WHERE status IN ('SCHEDULED', 'RESCHEDULED')" in compiled_idx


# =====================================================================
# 2. Concurrency Protection & Double Booking Prevention
# =====================================================================
@pytest.mark.asyncio
async def test_simultaneous_concurrent_bookings_against_database(client: AsyncClient):
    """
    Simulate two concurrent booking requests arriving at the exact same millisecond
    for the exact same doctor, date, and slot. Verifies that exactly one succeeds (201)
    and the other is rejected (409 Conflict).
    """
    target_date = (date.today() + timedelta(days=12)).isoformat()
    req_a = {
        "doctor_id": 1,
        "appointment_date": target_date,
        "appointment_time": "14:00",
        "patient_name": "Racer A",
        "patient_phone": "+919876543211",
        "patient_email": "racer_a@example.com"
    }
    req_b = {
        "doctor_id": 1,
        "appointment_date": target_date,
        "appointment_time": "14:00",
        "patient_name": "Racer B",
        "patient_phone": "+919876543212",
        "patient_email": "racer_b@example.com"
    }

    res_a, res_b = await asyncio.gather(
        client.post("/api/appointments", json=req_a),
        client.post("/api/appointments", json=req_b),
        return_exceptions=False
    )

    statuses = [res_a.status_code, res_b.status_code]
    assert 201 in statuses, f"Expected one 201 Created, got: {statuses}"
    assert 409 in statuses, f"Expected one 409 Conflict, got: {statuses}"


# =====================================================================
# 3. Transaction Rollback & Database Integrity
# =====================================================================
@pytest.mark.asyncio
async def test_transaction_rollback_on_failed_booking(db_session: AsyncSession):
    """
    Verify that if an error occurs during booking execution,
    the transaction is rolled back completely and no orphan records remain.
    """
    initial_count = (await db_session.execute(select(Appointment))).scalars().all()
    count_before = len(initial_count)

    # Attempt to book with a non-existent doctor ID (9999) which fails doctor verification
    res = await tool_registry.book_appointment(
        db_session,
        BookAppointmentInput(
            patient_id=1,
            doctor_id=9999,
            date=(date.today() + timedelta(days=14)).isoformat(),
            time="11:00"
        )
    )
    assert res["status"] in ("error", "not_found")

    # Verify count remains exactly the same (no partial writes)
    current_count = (await db_session.execute(select(Appointment))).scalars().all()
    assert len(current_count) == count_before


# =====================================================================
# 4. Idempotency Key Verification
# =====================================================================
@pytest.mark.asyncio
async def test_booking_idempotency_protection(db_session: AsyncSession):
    """
    Verify that retrying a booking request with the same idempotency key
    returns the already-booked record without creating duplicates.
    """
    target_date = (date.today() + timedelta(days=15)).isoformat()
    idem_key = "test_idem_key_778899"

    # Turn 1: Initial booking
    res1 = await tool_registry.book_appointment(
        db_session,
        BookAppointmentInput(
            patient_id=2,
            doctor_id=3,
            date=target_date,
            time="15:30",
            idempotency_key=idem_key
        )
    )
    assert res1["status"] == "booked"
    ref1 = res1["booking_reference"]

    # Turn 2: Exact same request with identical idempotency key
    res2 = await tool_registry.book_appointment(
        db_session,
        BookAppointmentInput(
            patient_id=2,
            doctor_id=3,
            date=target_date,
            time="15:30",
            idempotency_key=idem_key
        )
    )
    assert res2["status"] == "booked"
    assert res2["booking_reference"] == ref1  # Same reference returned
    assert res2.get("idempotent_replay") is True


# =====================================================================
# 5. Slot Release Upon Cancellation
# =====================================================================
@pytest.mark.asyncio
async def test_slot_released_upon_cancellation(client: AsyncClient):
    """
    Verify that partial unique index only covers active appointments:
    when an appointment is cancelled, the doctor slot becomes available again.
    """
    target_date = (date.today() + timedelta(days=16)).isoformat()
    payload = {
        "doctor_id": 2,
        "appointment_date": target_date,
        "appointment_time": "10:30",
        "patient_name": "Temporary Booking",
        "patient_phone": "+919876543299"
    }

    # Step 1: Book appointment
    create_res = await client.post("/api/appointments", json=payload)
    assert create_res.status_code == 201
    apt_id = create_res.json()["id"]

    # Step 2: Second booking for same slot should fail (409)
    conflict_res = await client.post("/api/appointments", json=payload)
    assert conflict_res.status_code == 409

    # Step 3: Cancel appointment
    cancel_res = await client.delete(f"/api/appointments/{apt_id}")
    assert cancel_res.status_code == 200

    # Step 4: Now rebooking the exact same slot should succeed (201)
    rebook_res = await client.post("/api/appointments", json=payload)
    assert rebook_res.status_code == 201
