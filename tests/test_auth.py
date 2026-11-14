"""Auth API: registration, login, sessions, role guards."""
from tests.conftest import login, register


def test_register_patient_returns_201(client):
    resp = client.post("/api/auth/register", json={
        "email": "new.patient@example.com",
        "password": "Password123",
        "full_name": "New Patient",
        "role": "patient",
    })
    assert resp.status_code == 201
    body = resp.get_json()["user"]
    assert body["email"] == "new.patient@example.com"
    assert body["role"] == "patient"
    assert "password" not in body and "password_hash" not in body


def test_register_doctor_without_specialty_fails(client):
    resp = client.post("/api/auth/register", json={
        "email": "dr@example.com",
        "password": "Password123",
        "full_name": "Dr. No Specialty",
        "role": "doctor",
    })
    assert resp.status_code == 400
    error = resp.get_json()["error"]
    assert "specialty" in error
    assert "Cardiology" in error  # the message shows an example to type


def test_duplicate_email_is_rejected(client):
    register(client, email="dup@example.com")
    resp = client.post("/api/auth/register", json={
        "email": "dup@example.com",
        "password": "Password123",
        "full_name": "Copy Cat",
        "role": "patient",
    })
    assert resp.status_code == 409


def test_short_password_is_rejected(client):
    resp = client.post("/api/auth/register", json={
        "email": "weak@example.com",
        "password": "short",
        "full_name": "Weak Pass",
        "role": "patient",
    })
    assert resp.status_code == 400


def test_login_success_and_me(client):
    register(client, email="me@example.com", full_name="Me Myself")
    user = login(client, "me@example.com")
    assert user["email"] == "me@example.com"

    resp = client.get("/api/auth/me")
    assert resp.status_code == 200
    assert resp.get_json()["user"]["full_name"] == "Me Myself"


def test_login_wrong_password(client):
    register(client, email="pw@example.com")
    resp = client.post("/api/auth/login", json={
        "email": "pw@example.com", "password": "WrongPass123",
    })
    assert resp.status_code == 401


def test_me_requires_login(client):
    resp = client.get("/api/auth/me")
    assert resp.status_code == 401
    assert "error" in resp.get_json()


def test_logout_clears_session(client):
    register(client, email="bye@example.com")
    login(client, "bye@example.com")

    resp = client.post("/api/auth/logout")
    assert resp.status_code == 200

    resp = client.get("/api/auth/me")
    assert resp.status_code == 401


def test_patient_cannot_create_slots(client):
    register(client, role="patient", email="nope@example.com")
    resp = client.post("/api/slots", json={
        "start_time": "2099-01-01T09:00:00Z",
        "end_time": "2099-01-01T09:30:00Z",
    })
    assert resp.status_code == 403


def test_appointments_require_login(client):
    resp = client.get("/api/appointments")
    assert resp.status_code == 401
