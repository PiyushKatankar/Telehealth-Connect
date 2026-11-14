"""HTML pages render correctly (Jinja templates + auth redirects)."""
from tests.conftest import login, register


def test_public_pages_render(client):
    for path, expected in [("/", "TeleHealth Connect"), ("/booking", "Book an appointment"),
                           ("/login", "Welcome back"), ("/register", "Create your account")]:
        resp = client.get(path)
        assert resp.status_code == 200, path
        assert expected.encode() in resp.data, path


def test_dashboard_requires_login(client):
    resp = client.get("/dashboard")
    assert resp.status_code == 302  # redirected to /login
    assert "/login" in resp.headers["Location"]


def test_dashboard_renders_for_patient(client):
    register(client, role="patient", email="pager@test.local")
    resp = client.get("/dashboard")
    assert resp.status_code == 200
    assert b"My appointments" in resp.data


def test_dashboard_shows_slot_manager_for_doctor(client):
    register(client, role="doctor", email="pager.doc@test.local", specialty="Testing")
    resp = client.get("/dashboard")
    assert resp.status_code == 200
    assert b"My availability" in resp.data


def test_chat_page_renders_for_participant(app, doctor_with_slots):
    doctor_client, doctor_user, slot_ids = doctor_with_slots
    patient = app.test_client()
    register(patient, email="pager.patient@test.local")
    appt_id = patient.post("/api/appointments", json={"slot_id": slot_ids[0]}
                           ).get_json()["appointment"]["id"]

    resp = patient.get(f"/chat/{appt_id}")
    assert resp.status_code == 200
    assert b"Appointment chat" in resp.data

    resp = doctor_client.get(f"/chat/{appt_id}")
    assert resp.status_code == 200


def test_chat_page_forbidden_for_outsider(app, doctor_with_slots):
    _client, _user, slot_ids = doctor_with_slots
    patient = app.test_client()
    register(patient, email="owner2@test.local")
    appt_id = patient.post("/api/appointments", json={"slot_id": slot_ids[0]}
                           ).get_json()["appointment"]["id"]

    outsider = app.test_client()
    register(outsider, email="outsider2@test.local")
    resp = outsider.get(f"/chat/{appt_id}")
    assert resp.status_code == 403
