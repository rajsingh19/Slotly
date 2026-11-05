import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_endpoints(client: AsyncClient):
    # Test root /health
    res1 = await client.get("/health")
    assert res1.status_code == 200
    data1 = res1.json()
    assert data1["status"] == "ok"
    assert data1["database"] == "healthy"
    assert "version" in data1
    assert "timestamp" in data1

    # Test /api/health
    res2 = await client.get("/api/health")
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2["status"] == "ok"


@pytest.mark.asyncio
async def test_root_index(client: AsyncClient):
    res = await client.get("/")
    assert res.status_code == 200
    data = res.json()
    assert "doctors" in data
    assert "appointments" in data
    assert "analytics" in data
