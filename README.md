# TeleHealth Connect

[![CI](https://github.com/YOUR_USERNAME/telehealth-connect/actions/workflows/ci.yml/badge.svg)](https://github.com/YOUR_USERNAME/telehealth-connect/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12-blue)
![License](https://img.shields.io/badge/license-MIT-green)

<!-- Replace YOUR_USERNAME in the badge URLs above after you push to GitHub. -->

A full-stack telehealth demo: patients book doctor appointments with **live slot
availability**, bookings are protected against double-booking by **SQL
transactions with row-level locking**, and each appointment gets a private
**symptom chat** over WebSocket. Role-based access control separates patients
from doctors on every endpoint.

> ⚠️ Demo/portfolio project — not for real clinical use.

## Features

- **Real-time slot availability** — every booking (and cancellation) is
  broadcast over Socket.IO to everyone viewing that doctor's calendar, so the
  slot grid updates without a refresh and without stale data.
- **Transaction-safe booking** — the booking endpoint locks the slot row
  (`SELECT ... FOR UPDATE`), re-checks availability inside the transaction,
  and is backed by a database constraint. Five patients racing for the same
  slot produce exactly one appointment — there's a test that proves it.
- **Symptom chat** — private Socket.IO room per appointment; messages are
  persisted and replayed as history when you join.
- **Role-based auth** — patients book and chat; doctors publish availability
  and manage their schedule. Session-based login (Flask-Login), enforced
  server-side with decorators.
- **Doctor directory + availability management** — doctors add/remove time
  windows from their dashboard; patients browse by specialty.

## Tech stack

| Layer     | Choice                                        |
| --------- | --------------------------------------------- |
| Backend   | Flask (app factory + blueprints)              |
| Database  | PostgreSQL (SQLAlchemy ORM) — SQLite for quick start & tests |
| Real-time | Flask-SocketIO (WebSocket, rooms per doctor/appointment) |
| Auth      | Flask-Login, session cookies, role decorators |
| Frontend  | Jinja2 templates + vanilla JS + a little CSS  |
| Testing   | pytest — API, auth, pages, chat, concurrency  |
| CI        | GitHub Actions (pytest on Python 3.10–3.12)   |

## How double-booking is prevented

The interesting part of this project. Booking runs inside one SQL transaction:

```sql
BEGIN;
  SELECT * FROM slots WHERE id = :slot_id FOR UPDATE;  -- row lock
  -- still 'open'? still in the future?
  UPDATE slots SET status = 'booked';
  INSERT INTO appointments (slot_id, patient_id, ...) VALUES (...);
COMMIT;
```

1. **Application layer** — `app/booking/service.py` locks the slot row with
   `SELECT ... FOR UPDATE`, so concurrent transactions serialize on that row
   under PostgreSQL. The second transaction sees `status = 'booked'` and
   returns HTTP 409 *before* attempting a write.
2. **Database layer** — a partial unique index
   (`CREATE UNIQUE INDEX ... ON appointments(slot_id) WHERE status != 'cancelled'`)
   means one *active* appointment per slot, enforced by the database itself.
   The `WHERE` clause lets a cancelled appointment's slot be booked again.
   This guard works even on SQLite (quick start), which has no row locks.

`tests/test_concurrency.py` fires 5 parallel booking requests at one slot and
asserts exactly one `201`, four `409`s, and a single row in the database.

## Quick start (SQLite, ~2 minutes)

```bash
git clone https://github.com/YOUR_USERNAME/telehealth-connect.git
cd telehealth-connect

python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt

python seed.py                   # creates tables + demo doctors/slots
python run.py                    # http://127.0.0.1:5000
```

No `.env` needed for the quick start — SQLite lives in `instance/`.

### Demo accounts

| Role    | Email                      | Password    |
| ------- | -------------------------- | ----------- |
| Patient | `patient@clinic.test`      | `Patient#123` |
| Doctor  | `doctor.aisha@clinic.test` | `Doctor#123`  |
| Doctor  | `doctor.daniel@clinic.test`| `Doctor#123`  |
| Doctor  | `doctor.elena@clinic.test` | `Doctor#123`  |

Open two browser windows (one logged in as a patient, one as a doctor) and
watch the booking/slot lists update live.

## Quick start (PostgreSQL + Docker)

```bash
docker compose up --build
# → http://localhost:8000  (Postgres starts first; seed.py runs on boot)
```

`docker-compose.yml` starts PostgreSQL 16 and the app, sets
`DATABASE_URL=postgresql+psycopg2://telehealth:telehealth@db:5432/telehealth`,
and runs the seed before gunicorn.

## Running the tests

```bash
pip install -r requirements.txt -r requirements-dev.txt
pytest                           # 36 tests incl. the concurrency race
```

## API reference

| Method   | Path                                   | Auth        | Purpose                          |
| -------- | -------------------------------------- | ----------- | -------------------------------- |
| `POST`   | `/api/auth/register`                   | —           | Create patient/doctor account    |
| `POST`   | `/api/auth/login`                      | —           | Log in (session cookie)          |
| `POST`   | `/api/auth/logout`                     | logged in   | Log out                          |
| `GET`    | `/api/auth/me`                         | logged in   | Current user                     |
| `GET`    | `/api/doctors`                         | —           | Doctor directory + open counts   |
| `GET`    | `/api/doctors/<id>/slots`              | —           | Doctor's future open slots       |
| `POST`   | `/api/slots`                           | doctor      | Create availability (overlap → 409) |
| `DELETE` | `/api/slots/<id>`                      | doctor      | Remove own open slot             |
| `POST`   | `/api/appointments`                    | patient     | Book a slot (transactional)      |
| `GET`    | `/api/appointments`                    | logged in   | My bookings / my schedule        |
| `POST`   | `/api/appointments/<id>/cancel`        | participant | Cancel (slot reopens)            |
| `GET`    | `/api/appointments/<id>/messages`      | participant | Chat history                     |

Errors are JSON: `{"error": "..."}` with proper status codes
(`400` validation, `401` not logged in, `403` wrong role, `404` not found,
`409` conflict — e.g. the slot was just taken).

## Socket.IO events

| Event             | Direction      | Payload / purpose                              |
| ----------------- | -------------- | ---------------------------------------------- |
| `subscribe_doctor`| client → server| `{doctor_id}` — join a doctor's availability room |
| `slot_update`     | server → room  | `{id, doctor_id, start_time, status}` — live availability |
| `join_chat`       | client → server| `{appointment_id}` — join chat (participants only) |
| `chat_joined`     | server → client| `{appointment_id, history[]}`                  |
| `send_message`    | client → server| `{appointment_id, body}` — persisted + broadcast |
| `chat_message`    | server → room  | full message record (both participants receive it) |
| `chat_error`      | server → client| non-participants / validation errors           |

## Project structure

```
telehealth-connect/
├── app/
│   ├── __init__.py          # app factory + error handlers
│   ├── extensions.py        # db / socketio / login_manager singletons
│   ├── models.py            # User, DoctorProfile, Slot, Appointment, Message
│   ├── auth/                # register/login/logout + role decorators
│   ├── booking/             # REST API + service.py (transaction-safe booking)
│   ├── chat/                # Socket.IO chat events + history API
│   ├── realtime/            # slot broadcasts + availability rooms
│   ├── main/                # page routes + /healthz
│   ├── templates/           # Jinja2 pages
│   └── static/              # CSS + vanilla JS (booking, chat, dashboard)
├── tests/                   # pytest: auth, booking, chat, pages, concurrency
├── .github/workflows/ci.yml # CI: pytest on Python 3.10–3.12
├── config.py                # dev / testing / production config
├── seed.py                  # demo accounts + one week of slots
├── run.py                   # dev server
├── wsgi.py                  # gunicorn entry point
├── Dockerfile / docker-compose.yml
└── requirements.txt
```

## Deployment notes

- Production entry point: `gunicorn -b 0.0.0.0:8000 -w 1 -k eventlet wsgi:app`
  (the Dockerfile does exactly this).
- Keep **one worker**, or set `SOCKETIO_MESSAGE_QUEUE=redis://...` — Socket.IO
  clients connected to different workers can't see each other's events
  without a shared message queue.
- Set a real `SECRET_KEY` (`python -c "import secrets; print(secrets.token_hex(32))"`)
  and restrict `cors_allowed_origins` in `app/extensions.py` to your origin.

## Honest security caveats

This is a portfolio demo, so a few things are deliberately simplified:
session-cookie auth without CSRF tokens (fine for a JSON API demo, add
tokens for production), no rate limiting, and the Socket.IO CORS policy is
`*` for easy local testing. The booking logic itself is deliberately *not*
simplified — that's the point of the project.

## License

[MIT](LICENSE)
