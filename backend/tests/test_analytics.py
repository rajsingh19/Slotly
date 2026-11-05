import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_analytics_api(client: AsyncClient):
    res = await client.get("/api/analytics")
    assert res.status_code == 200
    data = res.json()

    assert data["total_doctors"] == 5
    assert data["total_patients"] >= 3
    assert data["total_appointments"] >= 3
    assert "SCHEDULED" in data["appointments_by_status"]
    assert data["total_calls"] >= 1
    assert "doctor_workload" in data
    assert len(data["doctor_workload"]) == 5

