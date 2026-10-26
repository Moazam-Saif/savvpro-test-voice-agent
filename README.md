# Bright Smile Dental Voice Assistant

A deterministic, rule-based phone appointment assistant for Bright Smile Dental. The dialogue brain is written in our own Python code; no large language model makes decisions, chooses replies, or controls state transitions.

## Features

- End-to-end appointment booking with service, date, time, name, availability, lunch, clinic hours, lead-time, horizon, and conflict checks.
- Atomic confirmation snapshots: changes made after a readback invalidate the proposal and trigger fresh validation.
- Identity-guarded cancellation using an exact patient name plus date or a four-digit confirmation code.
- Emergency escalation for acute symptoms such as severe bleeding, facial swelling, and breathing difficulty.
- Deterministic NLU for natural English booking, cancellation, rescheduling, information, date, time, service, name, confirmation, and global command variants.
- Live decision trace showing normalized input, extracted values, polarity, rules fired, state transitions, and effects.
- Voice and typed input through a Next.js interface.
- Explicit microphone toggle: click `Speak` to start listening, see the transcript live, then click `Listening` to stop and submit.
- Stable speech lifecycle handling for browser recognition restarts, delayed events, microphone permission failures, and assistant speech output.

## Architecture

The system has three main layers:

- **Frontend**: Next.js 14, React, TypeScript, browser Web Speech API, live transcript, typed fallback, and decision trace UI.
- **API**: FastAPI REST endpoints for sessions, turns, health, and demo bookings.
- **Brain and domain**: deterministic Python NLU, policy/state machine, availability rules, booking service, and an in-memory repository.

The brain receives text plus optional speech confidence through injected ports. It does not import from the API layer or perform external I/O. Bookings are created only by `BookingService`, which revalidates the proposal before committing.

## Requirements

- Python 3.11 or newer
- Node.js 18 or newer
- Google Chrome or Microsoft Edge for browser speech recognition and synthesis

## Setup

### Backend

PowerShell:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
$env:PYTHONPATH = "$PWD\src"
python -m uvicorn assistant.main:app --host 127.0.0.1 --port 8000 --reload
```

The backend runs at `http://localhost:8000`.

- Health check: `http://localhost:8000/health`
- Demo bookings: `http://localhost:8000/api/demo/bookings`

If PowerShell blocks script activation, run `Set-ExecutionPolicy -Scope Process Bypass` for the current terminal, or use the environment's Python executable directly.

### Frontend

In a second terminal:

```powershell
cd frontend
npm install
npm run dev
```

Open `http://localhost:3000` in Chrome or Edge.

## Verification

Backend tests:

```powershell
cd backend
$env:PYTHONPATH = "$PWD\src"
python -m pytest -q
```

Frontend tests and type checking:

```powershell
cd frontend
npm test -- --run
npm run typecheck
```

The current verified suite contains **119 backend tests** and **6 frontend tests**. Backend coverage includes availability boundaries, DST arithmetic, API errors, deterministic behavior, import restrictions, booking scenarios, parser behavior, and 57 natural-English paraphrase cases.

Run the Windows project check from the repository root:

```powershell
.\scripts\check.ps1
```

## Demo Data

The demo endpoint exposes seeded fake appointments for cancellation and verification testing. Use `GET /api/demo/bookings` to retrieve current IDs, dates, and confirmation codes. Example patients include Sarah Thompson, Ali Raza, and Maria Gonzalez.

## Limitations

- Browser speech recognition and synthesis require a compatible Chrome or Edge environment.
- Voice input is half-duplex: the microphone is stopped while the assistant speaks.
- The repository and sessions are in memory; restarting the backend clears them.
- The model represents one dentist chair and one provider.
- Numeric dates use US month/day interpretation, such as `10/30`.
- English is the supported language, with `en-US`, `en-GB`, and `en-IN` locale options.
- No real patient information, payments, insurance, phone handoff, or persistent database is included.

See [DESIGN.md](./DESIGN.md) for the architecture and behavior specification, and [AI_USAGE.md](./AI_USAGE.md) for AI tooling transparency.
