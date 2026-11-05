import pytest
from datetime import date, timedelta
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_appointment_booking_and_lifecycle(client: AsyncClient):
    target_date = (date.today() + timedelta(days=3)).isoformat()

    # 1. Book appointment
    payload = {
        "doctor_id": 1,
        "appointment_date": target_date,
        "appointment_time": "14:00",
        "patient_name": "Eleanor Vance",
        "patient_phone": "+15557778888",
        "patient_email": "eleanor@example.com"
    }
    res = await client.post("/api/appointments", json=payload)
    assert res.status_code == 201
    apt = res.json()
    assert apt["status"] == "SCHEDULED"
    assert apt["booking_reference"].startswith("APT-")
    assert apt["appointment_date"] == target_date
    assert apt["appointment_time"] == "14:00"
    apt_id = apt["id"]

    # 2. Prevent Double Booking for the same doctor and time slot
    double_booking_payload = {
        "doctor_id": 1,
        "appointment_date": target_date,
        "appointment_time": "14:00",
        "patient_name": "Another Patient",
        "patient_phone": "+15559990000"
    }
    res_double = await client.post("/api/appointments", json=double_booking_payload)
    assert res_double.status_code == 409
    assert "already booked" in res_double.json()["detail"].lower()

    # 3. Prevent Duplicate Appointment for the same patient at the same date and time
    duplicate_payload = {
        "doctor_id": 2,
        "appointment_date": target_date,
        "appointment_time": "14:00",
        "patient_id": apt["patient_id"]
    }
    res_dup = await client.post("/api/appointments", json=duplicate_payload)
    assert res_dup.status_code == 409
    assert "duplicate appointment" in res_dup.json()["detail"].lower()

    # 4. List appointments with pagination
    list_res = await client.get(f"/api/appointments?appointment_date={target_date}&page=1&size=10")
    assert list_res.status_code == 200
    assert list_res.json()["total"] >= 1
    assert any(a["id"] == apt_id for a in list_res.json()["items"])

    # 5. Reschedule appointment
    reschedule_payload = {
        "appointment_time": "15:00",
        "status": "RESCHEDULED"
    }
    resched_res = await client.patch(f"/api/appointments/{apt_id}", json=reschedule_payload)
    assert resched_res.status_code == 200
    resched_data = resched_res.json()
    assert resched_data["appointment_time"] == "15:00"
    assert resched_data["status"] == "RESCHEDULED"

    # 6. Cancel appointment
    cancel_res = await client.delete(f"/api/appointments/{apt_id}")
    assert cancel_res.status_code == 200
    assert cancel_res.json()["success"] is True

    # Verify status is CANCELLED and slot 15:00 is freed
    get_res = await client.get(f"/api/appointments/{apt_id}")
    assert get_res.status_code == 200
    assert get_res.json()["status"] == "CANCELLED"

    # Now booking 15:00 is available again without conflict!
    rebook_res = await client.post("/api/appointments", json={
        "doctor_id": 1,
        "appointment_date": target_date,
        "appointment_time": "15:00",
        "patient_name": "New Comer",
        "patient_phone": "+15551112222"
    })
    assert rebook_res.status_code == 201


@pytest.mark.asyncio
async def test_appointment_rejects_past_date(client: AsyncClient):
    past_date = (date.today() - timedelta(days=2)).isoformat()
    payload = {
        "doctor_id": 1,
        "appointment_date": past_date,
        "appointment_time": "10:00",
        "patient_name": "Time Traveler",
        "patient_phone": "+15558889999"
    }
    res = await client.post("/api/appointments", json=payload)
    assert res.status_code == 422
