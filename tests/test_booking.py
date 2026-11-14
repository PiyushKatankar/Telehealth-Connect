"""Booking API: slot management, transactional booking, cancellation."""
from datetime import timedelta

from tests.conftest import login, register


def _iso(dt):
    return dt.isoformat(timespec="seconds") + "Z"


def _future_start(app, hours=24):
    from app.models import utc_now
    with app.app_context():
        return utc_now().replace(minute=0, second=0, microsecond=0) + timedelta(hours=hours)


# --------------------------------------------------------------------------
# Doctor directory + slot management
# --------------------------------------------------------------------------
def test_doctor_directory_lists_open_slot_count(app, doctor_with_slots):
    client, user, slot_ids = doctor_with_slots

    resp = client.get("/api/doctors")
    assert resp.status_code == 200
    doctors = resp.get_json()["doctors"]
    match = [d for d in doctors if d["id"] == user["id"]]
    assert len(match) == 1
    assert match[0]["open_slots"] == 3
    assert match[0]["specialty"] == "Testing"


def test_doctor_can_create_slot(app, doctor_client):
    client, user = doctor_client
    start = _future_start(app)
    resp = client.post("/api/slots", json={
        "start_time": _iso(start),
        "end_time": _iso(start + timedelta(minutes=30)),
    })
    assert resp.status_code == 201
    assert resp.get_json()["slot"]["status"] == "open"


def test_slot_must_end_after_start(app, doctor_client):
    client, _user = doctor_client
    start = _future_start(app)
    resp = client.post("/api/slots", json={
        "start_time": _iso(start),
        "end_time": _iso(start - timedelta(minutes=30)),  # backwards!
    })
    assert resp.status_code == 400


def test_slot_must_be_in_future(app, doctor_client):
    client, _user = doctor_client
    resp = client.post("/api/slots", json={
        "start_time": _iso(_future_start(app, hours=-48)),
        "end_time": _iso(_future_start(app, hours=-47)),
    })
    assert resp.status_code == 400


def test_overlapping_slot_is_rejected(app, doctor_with_slots):
    client, user, slot_ids = doctor_with_slots
    start = _future_start(app)  # same start as the fixture's first slot
    resp = client.post("/api/slots", json={
        "start_time": _iso(start),
        "end_time": _iso(start + timedelta(minutes=30)),
    })
    assert resp.status_code == 409


def test_doctor_can_delete_open_slot(app, doctor_with_slots):
    client, user, slot_ids = doctor_with_slots
    resp = client.delete(f"/api/slots/{slot_ids[0]}")
    assert resp.status_code == 200

    resp = client.get(f"/api/doctors/{user['id']}/slots")
    remaining = {s["id"] for s in resp.get_json()["slots"]}
    assert slot_ids[0] not in remaining


def test_cannot_delete_someone_elses_slot(app, doctor_with_slots):
    _client, _user, slot_ids = doctor_with_slots
    other = app.test_client()
    register(other, role="doctor", email="other.doc@test.local", specialty="X")
    resp = other.delete(f"/api/slots/{slot_ids[0]}")
    assert resp.status_code == 404


# --------------------------------------------------------------------------
# Booking (the double-booking-proof path)
# --------------------------------------------------------------------------
def test_patient_books_slot(app, doctor_with_slots):
    client, user, slot_ids = doctor_with_slots
    patient = app.test_client()
    register(patient, email="booker@test.local")

    resp = patient.post("/api/appointments", json={
        "slot_id": slot_ids[0], "symptoms": "Chest tightness when running.",
    })
    assert resp.status_code == 201
    appt = resp.get_json()["appointment"]
    assert appt["status"] == "scheduled"
    assert appt["doctor"]["id"] == user["id"]
    assert appt["symptoms"] == "Chest tightness when running."
    assert appt["slot"]["start_time"].endswith("Z")


def test_booked_slot_cannot_be_booked_again(app, doctor_with_slots):
    client, user, slot_ids = doctor_with_slots
    p1 = app.test_client()
    register(p1, email="first@test.local")
    p2 = app.test_client()
    register(p2, email="second@test.local")

    assert p1.post("/api/appointments", json={"slot_id": slot_ids[0]}).status_code == 201
    resp = p2.post("/api/appointments", json={"slot_id": slot_ids[0]})
    assert resp.status_code == 409
    assert "taken" in resp.get_json()["error"].lower()


def test_booking_unknown_slot_returns_404(app, patient_client):
    resp = patient_client.post("/api/appointments", json={"slot_id": 99999})
    assert resp.status_code == 404


def test_cancel_reopens_slot_for_others(app, doctor_with_slots):
    client, user, slot_ids = doctor_with_slots
    patient = app.test_client()
    register(patient, email="canceller@test.local")

    appt_id = patient.post("/api/appointments", json={"slot_id": slot_ids[0]}
                           ).get_json()["appointment"]["id"]

    resp = patient.post(f"/api/appointments/{appt_id}/cancel")
    assert resp.status_code == 200
    assert resp.get_json()["appointment"]["status"] == "cancelled"

    # Slot is open again and can be booked by someone else.
    resp = client.get(f"/api/doctors/{user['id']}/slots")
    assert slot_ids[0] in {s["id"] for s in resp.get_json()["slots"]}

    other = app.test_client()
    register(other, email="next@test.local")
    assert other.post("/api/appointments", json={"slot_id": slot_ids[0]}).status_code == 201


def test_non_participant_cannot_see_or_cancel(app, doctor_with_slots):
    client, user, slot_ids = doctor_with_slots
    patient = app.test_client()
    register(patient, email="owner@test.local")
    appt_id = patient.post("/api/appointments", json={"slot_id": slot_ids[0]}
                           ).get_json()["appointment"]["id"]

    stranger = app.test_client()
    register(stranger, email="stranger@test.local")

    assert stranger.post(f"/api/appointments/{appt_id}/cancel").status_code == 404
    assert stranger.get(f"/api/appointments/{appt_id}/messages").status_code == 403


def test_appointment_lists_are_role_scoped(app, doctor_with_slots):
    client, user, slot_ids = doctor_with_slots
    patient = app.test_client()
    register(patient, email="scoped@test.local")
    patient.post("/api/appointments", json={"slot_id": slot_ids[0]})

    seen_by_patient = patient.get("/api/appointments").get_json()["appointments"]
    assert len(seen_by_patient) == 1

    seen_by_doctor = client.get("/api/appointments").get_json()["appointments"]
    assert len(seen_by_doctor) == 1
    assert seen_by_doctor[0]["patient"]["full_name"] == "Test User"
    assert seen_by_doctor[0]["doctor"]["id"] == user["id"]
