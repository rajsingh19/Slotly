import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_calls_and_events_api(client: AsyncClient):
    # 1. List calls
    list_res = await client.get("/api/calls?page=1&size=10")
    assert list_res.status_code == 200
    data = list_res.json()
    assert "items" in data
    assert data["total"] >= 1
    assert data["items"][0]["caller_number"] == "+15551234567"

    # 2. Create a new call session
    create_payload = {
        "caller_number": "+15557776666",
        "call_direction": "INBOUND",
        "transcript": "Caller: Do you have a pediatrician available?",
        "status": "COMPLETED",
        "estimated_cost": 0.035
    }
    create_res = await client.post("/api/calls", json=create_payload)
    assert create_res.status_code == 201
    call = create_res.json()
    assert call["caller_number"] == "+15557776666"
    call_id = call["id"]

    # 3. Add an event to this call session
    event_res = await client.post(
        f"/api/calls/{call_id}/events?event_type=SPEECH_RECOGNIZED&event_data=transcribed_sample"
    )
    assert event_res.status_code == 201
    event = event_res.json()
    assert event["event_type"] == "SPEECH_RECOGNIZED"
    assert event["call_session_id"] == call_id
