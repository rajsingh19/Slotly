# AI Hospital Receptionist & Appointment Booking Voice Agent

A production-oriented MVP of an AI voice calling and hospital receptionist system designed to communicate with patients, answer hospital-related inquiries, check real-time doctor availability, book appointments, reschedule and cancel visits, and triage medical emergencies.

Built with **FastAPI**, **React + Vite + TypeScript + Tailwind CSS**, **Pipecat** frame-compatible voice orchestration, **Sarvam AI** STT & Bulbul TTS, **PostgreSQL**, **Redis**, and optional **Plivo** telephony.

---

## Features

- **Empathetic AI Receptionist (Maya)**: Answers clinical department inquiries, visiting hours, insurance acceptance, parking, and location.
- **Voice-Driven Appointment Booking**: Hands-free slot discovery, reservation, and instant booking confirmation.
- **Rescheduling & Cancellation**: Look up existing appointments by patient phone or reference number (`APT-...`) and modify bookings.
- **Emergency Triage Routing**: Detects life-threatening symptoms (chest pain, stroke, breathing distress) and immediately provides 24/7 ER guidance.
- **Pipecat Streaming Architecture**: WebSocket audio frame streaming with real-time audio waveform visualizer and turn-taking latency tracking.
- **Sarvam AI Integration**:
  - **STT**: Sarvam AI (`saarika:v2`) for Indian & global English.
  - **TTS**: Sarvam AI Bulbul (`bulbul:v1`) expressive voice synthesis with the `ananya` speaker profile.
- **Zero-Dependency Local Development**: Built-in SQLite async fallback, In-Memory cache fallback, and intelligent dialogue engine so the full system runs locally without requiring paid API keys or external databases.

---

## Monorepo Structure

```text
voice-agent/
|-- backend/                    # Python FastAPI Backend
|   |-- app/
|   |   |-- api/                # REST & WebSocket Endpoints (v1)
|   |   |-- core/               # Settings, structured logging, database & cache
|   |   |-- models/             # SQLAlchemy ORM models (Doctor, Slot, Appointment, CallLog)
|   |   |-- schemas/            # Pydantic request/response validation
|   |   |-- seeds/              # Initial hospital departments, doctors, slots & FAQs
|   |   |-- services/           # Business logic, voice adapters & telephony
|   |   |   |-- voice/          # STT (Sarvam), TTS (Bulbul), LLM & Pipecat pipeline
|   |   |   `-- telephony/      # Plivo webhook handlers
|   |   `-- main.py             # FastAPI entry point & lifespan
|   |-- tests/                  # Automated pytest suite
|   |-- requirements.txt        # Python dependencies
|   `-- pytest.ini              # Pytest configuration
|-- frontend/                   # React 18 + Vite + TypeScript + Tailwind CSS
|   |-- src/
|   |   |-- components/         # VoiceConsole, DoctorsList, AppointmentsView, Header
|   |   |-- hooks/              # useVoiceCall (Web Audio API & WebSocket stream)
|   |   |-- services/           # REST API client
|   |   |-- types/              # TypeScript definitions
|   |   |-- App.tsx             # Main dashboard navigation
|   |   `-- main.tsx            # Entry point
|   |-- package.json
|   |-- tailwind.config.js
|   `-- vite.config.ts
|-- infra/                      # Infrastructure & Containerization
|   |-- docker-compose.yml      # Multi-container setup (Backend, Frontend, Postgres, Redis)
|   |-- Dockerfile.backend      # Production Python 3.12 slim backend image
|   |-- Dockerfile.frontend     # Multi-stage Node build & Nginx alpine image
|   `-- nginx.conf              # SPA routing and WebSocket reverse proxy
|-- docs/                       # Architecture & Documentation
|   |-- ARCHITECTURE.md         # Architecture & sequence diagrams
|   |-- API.md                  # REST & WebSocket protocol specifications
|   `-- SARVAM_AND_VOICE_GUIDE.md # Sarvam AI STT & Bulbul TTS guide
|-- .env.example                # Documented configuration template
|-- .env                        # Local development configuration
`-- .gitignore                  # Git ignore rules
```

---

## Quickstart (Local Development)

### 1. Prerequisites
- **Python**: 3.10+ (tested on Python 3.12 and 3.14)
- **Node.js**: v18+ and npm
- Git

### 2. Configure Environment
Copy `.env.example` to `.env` (already pre-configured for instant zero-dependency local development):
```bash
cp .env.example .env
```

### 3. Backend Setup
```bash
cd backend
python -m venv venv

# On Windows:
.\venv\Scripts\activate
# On Linux/macOS:
# source venv/bin/activate

pip install -r requirements.txt
```

Run database seeding and start the FastAPI server:
```bash
# From workspace root:
$env:PYTHONPATH="backend"
uvicorn app.main:app --reload --port 8000
```
- API Docs: [http://localhost:8000/docs](http://localhost:8000/docs)
- Health Check: [http://localhost:8000/api/v1/health](http://localhost:8000/api/v1/health)

### 4. Frontend Setup
In a new terminal:
```bash
cd frontend
npm install
npm run dev
```
Open [http://localhost:5173](http://localhost:5173) in your browser.

---

## Running Automated Tests

Run the backend test suite:
```bash
# On Windows PowerShell:
$env:PYTHONPATH="backend"; .\backend\venv\Scripts\python -m pytest backend/tests -v

# On Linux/macOS:
PYTHONPATH=backend pytest backend/tests -v
```

All 10 automated test suites verify:
- Health check & uptime
- Doctor listing & specialty filtering
- Real-time time slot availability
- Appointment booking, slot locking, rescheduling, and cancellation
- Voice mock adapters, session creation, and conversation turn processing.

---

## Docker Compose Deployment

To deploy the entire production stack (PostgreSQL, Redis, FastAPI Backend, React Frontend via Nginx):

```bash
docker compose -f infra/docker-compose.yml up --build -d
```

Services will be accessible at:
- **Web Application**: [http://localhost](http://localhost) (Port 80)
- **FastAPI API**: [http://localhost:8000](http://localhost:8000)
- **PostgreSQL**: `localhost:5432`
- **Redis**: `localhost:6379`

To view container logs:
```bash
docker compose -f infra/docker-compose.yml logs -f
```

---

## Configuration Reference

| Variable | Description | Default |
|---|---|---|
| `DATABASE_URL` | PostgreSQL or SQLite database connection string | `sqlite+aiosqlite:///./hospital.db` |
| `REDIS_URL` | Redis cache connection string | `redis://localhost:6379/0` |
| `REDIS_ENABLED` | Enable Redis (in-memory cache used if false) | `false` |
| `LLM_PROVIDER` | LLM choice (`mock`, `gemini`, `openai`, `groq`) | `mock` |
| `GEMINI_API_KEY` | Google Gemini API key (optional) | `""` |
| `SARVAM_API_KEY` | Sarvam AI STT & Bulbul TTS key (optional) | `""` |
| `SARVAM_TTS_SPEAKER` | Bulbul voice speaker (`ananya`, `aditya`) | `ananya` |
| `PLIVO_ENABLED` | Telephony via Plivo (optional) | `false` |

---

## Telephony via Plivo (Optional)

When deploying with a live telephone number:
1. Set `PLIVO_ENABLED=true`, `PLIVO_AUTH_ID`, `PLIVO_AUTH_TOKEN`, and `PLIVO_PHONE_NUMBER` in `.env`.
2. Configure your Plivo number's Answer URL to:
   `https://<your-public-domain>/api/v1/telephony/plivo/answer`
3. Speech inputs are processed by Maya and spoken back in real time over the telephone line.

---

## License

MIT License. Designed and built for hospital reception and patient voice automation.
