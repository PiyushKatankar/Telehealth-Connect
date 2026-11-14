"""Shared pytest fixtures.

Every test runs against its own temporary SQLite file database (fast, and
it supports the multi-connection concurrency test). The app code itself is
database-agnostic — the same tests would pass against PostgreSQL.
"""
import pytest


@pytest.fixture()
def app(tmp_path, monkeypatch):
    """Fresh app + empty database for one test.

    Important: do NOT keep an app context open while the test body runs —
    Flask reuses an already-active app context for test-client requests,
    which would make every request share one `g` (and Flask-Login caches
    the logged-in user on `g`, leaking sessions between test clients).
    """
    monkeypatch.setenv("TEST_DATABASE_URL", f"sqlite:///{tmp_path / 'test.db'}")

    from app import create_app
    from app.extensions import db

    application = create_app("testing")
    with application.app_context():
        db.create_all()
    yield application
    with application.app_context():
        db.session.remove()
        db.engine.dispose()


@pytest.fixture()
def client(app):
    return app.test_client()


# --------------------------------------------------------------------------
# Account helpers (used by most test modules)
# --------------------------------------------------------------------------
def register(client, role="patient", email=None, password="Password123",
             full_name="Test User", autologin=True, **extra):
    payload = {
        "email": email or f"{role}-{id(client)}@test.local",
        "password": password,
        "full_name": full_name,
        "role": role,
        **extra,
    }
    resp = client.post("/api/auth/register", json=payload)
    assert resp.status_code == 201, resp.get_json()
    user = resp.get_json()["user"]
    if autologin:
        # Mirror the frontend: register then log in to get a session cookie.
        login(client, user["email"], password)
    return user


def login(client, email, password="Password123"):
    resp = client.post("/api/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.get_json()
    return resp.get_json()["user"]


@pytest.fixture()
def patient_client(app):
    """A logged-in patient."""
    c = app.test_client()
    register(c, role="patient")
    return c


@pytest.fixture()
def doctor_client(app):
    """A logged-in doctor (no slots yet)."""
    c = app.test_client()
    user = register(c, role="doctor", specialty="Testing", bio="Dr. Test")
    return c, user


@pytest.fixture()
def doctor_with_slots(app, doctor_client):
    """Doctor (logged in) with three future open slots created directly in the DB."""
    from datetime import timedelta

    from app.extensions import db
    from app.models import Slot, utc_now

    client, user = doctor_client
    with app.app_context():
        base = utc_now().replace(minute=0, second=0, microsecond=0) + timedelta(days=1)
        slots = [
            Slot(doctor_id=user["id"],
                 start_time=base + timedelta(hours=offset),
                 end_time=base + timedelta(hours=offset, minutes=30))
            for offset in range(3)
        ]
        db.session.add_all(slots)
        db.session.commit()
        slot_ids = [s.id for s in slots]
    return client, user, slot_ids


@pytest.fixture()
def socket_client_factory(app):
    """Make Socket.IO test clients that share a Flask session's cookies."""
    def _make(flask_client):
        from flask_socketio import SocketIOTestClient

        from app.extensions import socketio

        return SocketIOTestClient(app, socketio, flask_test_client=flask_client)
    return _make
