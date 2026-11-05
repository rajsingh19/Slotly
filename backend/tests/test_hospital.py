import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_hospital_info_endpoint(client: AsyncClient):
    response = await client.get("/api/hospital")
    assert response.status_code == 200
    data = response.json()
    assert "id" in data
    assert "name" in data
    assert "address" in data
    assert "contact_number" in data
    assert data["name"] == "Apex Multi-Specialty Hospital"
    assert "Evergreen" in data["address"]
    assert "+1-800-555-0199" in data["contact_number"]
