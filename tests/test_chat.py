"""Symptom chat: Socket.IO rooms, persistence, membership enforcement."""
import pytest
from flask_socketio import SocketIOTestClient

from tests.conftest import register


@pytest.fixture()
def booked_appointment(app, doctor_with_slots):
    """A scheduled appointment + the two logged-in participants."""
    doctor_client, doctor_user, slot_ids = doctor_with_slots
    patient = app.test_client()
    register(patient, email="chatty.patient@test.local")

    resp = patient.post("/api/appointments",
                        json={"slot_id": slot_ids[0], "symptoms": "Sore throat."})
    assert resp.status_code == 201
    return {
        "doctor_client": doctor_client,
        "doctor_user": doctor_user,
        "patient_client": patient,
        "appointment_id": resp.get_json()["appointment"]["id"],
    }


def test_participants_join_and_exchange_messages(app, booked_appointment, socket_client_factory):
    info = booked_appointment
    appt_id = info["appointment_id"]

    patient_sock = socket_client_factory(info["patient_client"])
    doctor_sock = socket_client_factory(info["doctor_client"])

    patient_sock.emit("join_chat", {"appointment_id": appt_id})
    joined = [m for m in patient_sock.get_received() if m["name"] == "chat_joined"]
    assert joined and joined[0]["args"][0]["appointment_id"] == appt_id

    doctor_sock.emit("join_chat", {"appointment_id": appt_id})
    doctor_sock.get_received()

    patient_sock.emit("send_message",
                      {"appointment_id": appt_id, "body": "It hurts when I swallow."})
    received = doctor_sock.get_received()
    messages = [m for m in received if m["name"] == "chat_message"]
    assert len(messages) == 1
    assert messages[0]["args"][0]["body"] == "It hurts when I swallow."
    assert messages[0]["args"][0]["sender_role"] == "patient"


def test_message_history_is_persisted(app, booked_appointment, socket_client_factory):
    info = booked_appointment
    appt_id = info["appointment_id"]

    sock = socket_client_factory(info["patient_client"])
    sock.emit("join_chat", {"appointment_id": appt_id})
    sock.get_received()
    sock.emit("send_message", {"appointment_id": appt_id, "body": "Hello doctor!"})
    sock.get_received()

    resp = info["patient_client"].get(f"/api/appointments/{appt_id}/messages")
    assert resp.status_code == 200
    history = resp.get_json()["messages"]
    assert len(history) == 1
    assert history[0]["body"] == "Hello doctor!"


def test_join_replays_history(app, booked_appointment, socket_client_factory):
    info = booked_appointment
    appt_id = info["appointment_id"]

    patient_sock = socket_client_factory(info["patient_client"])
    patient_sock.emit("join_chat", {"appointment_id": appt_id})
    patient_sock.get_received()
    patient_sock.emit("send_message", {"appointment_id": appt_id, "body": "first"})
    patient_sock.get_received()

    late_doctor = app.test_client()
    register(late_doctor, role="doctor", email="late.doc@test.local", specialty="ENT")
    # Not a participant of THIS appointment — should be rejected below.

    owner_doctor_sock = socket_client_factory(info["doctor_client"])
    owner_doctor_sock.emit("join_chat", {"appointment_id": appt_id})
    received = owner_doctor_sock.get_received()
    joined = [m for m in received if m["name"] == "chat_joined"]
    assert joined
    history = joined[0]["args"][0]["history"]
    assert len(history) == 1 and history[0]["body"] == "first"


def test_outsider_cannot_join_chat(app, booked_appointment, socket_client_factory):
    appt_id = booked_appointment["appointment_id"]

    outsider_http = app.test_client()
    register(outsider_http, email="outsider@test.local")
    outsider_sock = socket_client_factory(outsider_http)

    outsider_sock.emit("join_chat", {"appointment_id": appt_id})
    received = outsider_sock.get_received()
    errors = [m for m in received if m["name"] == "chat_error"]
    joined = [m for m in received if m["name"] == "chat_joined"]
    assert errors and not joined


def test_empty_message_is_rejected(app, booked_appointment, socket_client_factory):
    info = booked_appointment
    appt_id = info["appointment_id"]

    sock = socket_client_factory(info["patient_client"])
    sock.emit("join_chat", {"appointment_id": appt_id})
    sock.get_received()
    sock.emit("send_message", {"appointment_id": appt_id, "body": "   "})

    received = sock.get_received()
    assert any(m["name"] == "chat_error" for m in received)

    resp = info["patient_client"].get(f"/api/appointments/{appt_id}/messages")
    assert resp.get_json()["messages"] == []


def test_message_history_requires_login(app, booked_appointment):
    appt_id = booked_appointment["appointment_id"]
    resp = app.test_client().get(f"/api/appointments/{appt_id}/messages")
    assert resp.status_code == 401
