import pytest
from datetime import date, timedelta
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_get_doctor_availability(client: AsyncClient):
    # Fetch doctor
    docs_res = await client.get("/api/doctors?specialization=Cardiology")
    doc_id = docs_res.json()["items"][0]["id"]

    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    res = await client.get(f"/api/availability?doctor_id={doc_id}&date={tomorrow}")
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 1
    doc_avail = data[0]
    assert doc_avail["doctor_id"] == doc_id
    assert len(doc_avail["slots"]) > 0

    # In seed data, tomorrow 10:00 is booked for Doctor 1 (Dr. Rajesh Sharma)
    slot_10 = next((s for s in doc_avail["slots"] if s["time"] == "10:00"), None)
    assert slot_10 is not None
    assert slot_10["is_available"] is False

    # Other slots should be available
    slot_09 = next((s for s in doc_avail["slots"] if s["time"] == "09:00"), None)
    assert slot_09 is not None
    assert slot_09["is_available"] is True

