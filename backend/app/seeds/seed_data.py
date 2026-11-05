import json
from datetime import date, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.hospital import Hospital
from app.models.doctor import Doctor
from app.models.patient import Patient
from app.models.appointment import Appointment, generate_booking_reference
from app.models.call_session import CallSession, CallEvent
from app.core.logging import get_logger

logger = get_logger(__name__)

STANDARD_SLOTS = [
    "09:00", "09:30", "10:00", "10:30",
    "11:00", "11:30", "14:00", "14:30",
    "15:00", "15:30", "16:00"
]


async def seed_initial_data(db: AsyncSession) -> None:
    """
    Seed initial hospital, 5 doctors with structured availability slots,
    sample patients, and appointments.
    Idempotent: skips if doctors already exist.
    """
    existing_doc = await db.execute(select(Doctor))
    if existing_doc.scalars().first():
        logger.info("Database already contains doctor data. Skipping seeding.")
        return

    logger.info("Seeding initial hospital, 5 doctors, sample patients, and appointments...")

    # 1. Hospital
    hospital = Hospital(
        name="Apex Multi-Specialty Hospital",
        address="742 Evergreen Healthcare Blvd, Medical District",
        contact_number="+1-800-555-0199",
    )
    db.add(hospital)

    # 2. Five Doctors across diverse clinical specializations
    doctors = [
        Doctor(
            name="Dr. Rajesh Sharma",
            specialization="Cardiology",
            availability=json.dumps({
                "days": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"],
                "slots": STANDARD_SLOTS,
                "room": "Room 204, Wing A"
            }),
            consultation_fee=80.0,
            is_active=True,
        ),
        Doctor(
            name="Dr. Priya Menon",
            specialization="Pediatrics",
            availability=json.dumps({
                "days": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"],
                "slots": STANDARD_SLOTS,
                "room": "Room 310, Wing C"
            }),
            consultation_fee=60.0,
            is_active=True,
        ),
        Doctor(
            name="Dr. Vikram Malhotra",
            specialization="Orthopedics",
            availability=json.dumps({
                "days": ["Tuesday", "Thursday", "Saturday"],
                "slots": ["10:00", "10:30", "11:00", "11:30", "14:00", "14:30", "15:00", "15:30"],
                "room": "Room 112, Wing B"
            }),
            consultation_fee=75.0,
            is_active=True,
        ),
        Doctor(
            name="Dr. Ananya Roy",
            specialization="Neurology",
            availability=json.dumps({
                "days": ["Monday", "Wednesday", "Friday"],
                "slots": ["09:30", "10:00", "10:30", "11:00", "14:30", "15:00", "15:30"],
                "room": "Room 408, Wing A"
            }),
            consultation_fee=90.0,
            is_active=True,
        ),
        Doctor(
            name="Dr. Sunita Patel",
            specialization="Dermatology",
            availability=json.dumps({
                "days": ["Monday", "Tuesday", "Thursday", "Friday"],
                "slots": ["11:00", "11:30", "14:00", "14:30", "15:00", "15:30", "16:00"],
                "room": "Room 214, Wing B"
            }),
            consultation_fee=65.0,
            is_active=True,
        ),
    ]

    for doc in doctors:
        db.add(doc)

    await db.flush()  # assign IDs

    # 3. Sample Patients
    patients = [
        Patient(name="John Doe", phone_number="+15551234567", email="john.doe@example.com"),
        Patient(name="Jane Smith", phone_number="+15559876543", email="jane.smith@example.com"),
        Patient(name="Robert Johnson", phone_number="+15553334444", email="robert.j@example.com"),
    ]
    for p in patients:
        db.add(p)

    await db.flush()

    # 4. Sample Appointments (today and tomorrow)
    tomorrow = date.today() + timedelta(days=1)
    day_after = date.today() + timedelta(days=2)

    sample_appointments = [
        Appointment(
            patient_id=patients[0].id,
            doctor_id=doctors[0].id,
            appointment_date=tomorrow,
            appointment_time="10:00",
            status="SCHEDULED",
            booking_reference="APT-SAMPLE-0001",
        ),
        Appointment(
            patient_id=patients[1].id,
            doctor_id=doctors[1].id,
            appointment_date=tomorrow,
            appointment_time="11:00",
            status="SCHEDULED",
            booking_reference="APT-SAMPLE-0002",
        ),
        Appointment(
            patient_id=patients[2].id,
            doctor_id=doctors[2].id,
            appointment_date=day_after,
            appointment_time="14:00",
            status="SCHEDULED",
            booking_reference="APT-SAMPLE-0003",
        ),
    ]
    for apt in sample_appointments:
        db.add(apt)

    # 5. Sample Call Sessions & Events
    call = CallSession(
        caller_number="+15551234567",
        call_direction="INBOUND",
        duration_seconds=95,
        transcript="Caller: I'd like to book an appointment with Dr. Sharma tomorrow morning.\nMaya: I found an open slot at 10:00 AM. Appointment booked with reference APT-SAMPLE-0001.",
        status="COMPLETED",
        estimated_cost=0.045,
    )
    db.add(call)
    await db.flush()

    event1 = CallEvent(
        call_session_id=call.id,
        event_type="SPEECH_RECOGNIZED",
        event_data=json.dumps({"transcript": "I'd like to book an appointment with Dr. Sharma"}),
    )
    event2 = CallEvent(
        call_session_id=call.id,
        event_type="TOOL_EXECUTED",
        event_data=json.dumps({"tool": "book_appointment", "result": "APT-SAMPLE-0001"}),
    )
    db.add(event1)
    db.add(event2)

    await db.commit()
    logger.info("Successfully seeded database with hospital, 5 doctors, patients, appointments, and calls.")
