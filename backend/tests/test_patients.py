import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_and_get_patient(client: AsyncClient):
    payload = {
        "name": "Michael Chang",
        "phone_number": "+15554445555",
        "email": "michael.chang@example.com"
    }
    res = await client.post("/api/patients", json=payload)
    assert res.status_code == 201
    data = res.json()
    assert data["name"] == "Michael Chang"
    assert data["phone_number"] == "+15554445555"
    patient_id = data["id"]

    # Retrieve patient by ID
    get_res = await client.get(f"/api/patients/{patient_id}")
    assert get_res.status_code == 200
    assert get_res.json()["id"] == patient_id


@pytest.mark.asyncio
async def test_patient_phone_validation_rejects_invalid_numbers(client: AsyncClient):
    # Invalid: too short or non-digits
    invalid_payload = {
        "name": "Bad Phone",
        "phone_number": "123",
        "email": "bad@example.com"
    }
    res = await client.post("/api/patients", json=invalid_payload)
    assert res.status_code == 422
