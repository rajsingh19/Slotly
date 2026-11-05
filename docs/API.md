# Hospital Voice Agent - API Specifications

All endpoints are prefixed with `/api/v1`.

## 1. Health Checks

### `GET /api/v1/health`
Checks health of database, cache, and voice adapters.

**Sample Response (200 OK):**
```json
{
  "success": true,
  "message": "AI Hospital Receptionist Voice Agent is operating normally",
  "data": {
    "status": "ok",
    "version": "1.0.0",
    "environment": "development",
    "database": "healthy",
    "cache": "healthy",
    "voice_stt": "sarvam_ai",
    "voice_tts": "sarvam_bulbul (ananya)",
    "llm_provider": "gemini (gemini-1.5-flash)",
    "uptime_seconds": 342.12
  }
}
```

---

## 2. Doctors & Schedules

### `GET /api/v1/doctors`
Query parameters:
- `specialty` (optional): Filter by medical specialty (e.g. `Cardiology`, `Pediatrics`)
- `department` (optional): Filter by hospital department
- `search` (optional): Search doctor name or qualification

### `GET /api/v1/doctors/slots/available`
Query parameters:
- `doctor_id` (optional): Filter by doctor
- `specialty` (optional): Specialty
- `target_date` (optional): YYYY-MM-DD

**Sample Response:**
```json
{
  "success": true,
  "data": [
    {
      "id": 14,
      "doctor_id": 1,
      "slot_date": "2026-11-06",
      "start_time": "10:00 AM",
      "end_time": "10:30 AM",
      "is_booked": false
    }
  ]
}
```

---

## 3. Appointments Management

### `POST /api/v1/appointments`
Book a doctor consultation slot.

**Request Body:**
```json
{
  "patient_name": "Sarah Connor",
  "patient_phone": "+1-555-0144",
  "patient_email": "sarah@example.com",
  "patient_age": 34,
  "patient_gender": "Female",
  "doctor_id": 1,
  "slot_id": 14,
  "reason_for_visit": "High blood pressure follow-up"
}
```

### `PATCH /api/v1/appointments/{identifier}/reschedule`
Reschedule an appointment by ID or appointment reference number.

**Request Body:**
```json
{
  "new_slot_id": 18,
  "reason": "Patient requested later afternoon slot"
}
```

### `PATCH /api/v1/appointments/{identifier}/cancel`
Cancel an appointment.

**Request Body:**
```json
{
  "cancellation_reason": "Patient resolved symptoms"
}
```

---

## 4. Voice Streaming & WebSocket

### `POST /api/v1/voice/session`
Initiate a voice calling session. Returns `session_id` and WebSocket connection URL.

### `WebSocket /api/v1/voice/ws/{session_id}`
Real-time bidirectional WebSocket voice streaming.

**Client to Server Frame (Audio or Text):**
```json
{
  "type": "audio",
  "data": "<base64_encoded_wav_bytes>",
  "sample_rate": 16000,
  "format": "wav"
}
```
Or text turn:
```json
{
  "type": "text",
  "data": "Book an appointment with Dr. Sharma tomorrow"
}
```

**Server to Client Frame (Spoken text, action, and synthesized audio):**
```json
{
  "type": "text",
  "role": "assistant",
  "data": "Your appointment with Dr. Rajesh Sharma has been booked for Friday at 10:00 AM. Your reference number is APT-20261106-9A1F3C.",
  "latency_ms": 312.4,
  "action_type": "BOOKING_CONFIRMED",
  "action_payload": {
    "appointment_number": "APT-20261106-9A1F3C",
    "doctor_name": "Dr. Rajesh Sharma"
  }
}
```
Followed immediately by audio chunk:
```json
{
  "type": "audio",
  "role": "assistant",
  "data": "<base64_encoded_pcm_wav_audio>",
  "format": "wav",
  "sample_rate": 16000
}
```

---

## 5. Telephony (Plivo Webhooks)

- `POST /api/v1/telephony/plivo/answer`: Connects inbound telephone call, generates Plivo XML welcome.
- `POST /api/v1/telephony/plivo/event`: Receives Plivo transcribed speech, executes voice turn, returns reply XML.
