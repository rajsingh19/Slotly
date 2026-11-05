import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_list_doctors_paginated(client: AsyncClient):
    response = await client.get("/api/doctors?page=1&size=10")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert data["total"] == 5
    assert len(data["items"]) == 5
    assert data["page"] == 1
    assert data["size"] == 10

    # Verify doctor fields
    first_doc = data["items"][0]
    assert "name" in first_doc
    assert "specialization" in first_doc
    assert "availability" in first_doc
    assert "consultation_fee" in first_doc
    assert first_doc["is_active"] is True


@pytest.mark.asyncio
async def test_filter_doctors_by_specialization(client: AsyncClient):
    response = await client.get("/api/doctors?specialization=Cardiology")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["specialization"] == "Cardiology"
    assert "Rajesh Sharma" in data["items"][0]["name"]


@pytest.mark.asyncio
async def test_get_doctor_by_id(client: AsyncClient):
    # Fetch first doctor
    list_res = await client.get("/api/doctors")
    first_id = list_res.json()["items"][0]["id"]

    res = await client.get(f"/api/doctors/{first_id}")
    assert res.status_code == 200
    doctor = res.json()
    assert doctor["id"] == first_id

    # Non-existent ID returns 404
    notFound = await client.get("/api/doctors/9999")
    assert notFound.status_code == 404
