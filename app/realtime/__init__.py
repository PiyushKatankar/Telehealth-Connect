"""Real-time broadcasts + availability subscriptions over Socket.IO.

Rooms:
  doctor-<id>      everyone viewing a doctor's availability (booking page,
                   the doctor's dashboard)
  appointment-<id> the patient + doctor of one appointment (chat)

``socketio.emit`` (the instance method) is safe to call from plain HTTP
request handlers — it broadcasts through the running server without
needing a socket context.
"""
from flask_socketio import emit, join_room, leave_room

from app.extensions import socketio
from app.models import Slot

DOCTOR_ROOM = "doctor-{doctor_id}"
APPOINTMENT_ROOM = "appointment-{appointment_id}"


def doctor_room_id(doctor_id: int) -> str:
    return DOCTOR_ROOM.format(doctor_id=doctor_id)


def appointment_room_id(appointment_id: int) -> str:
    return APPOINTMENT_ROOM.format(appointment_id=appointment_id)


def broadcast_slot_update(slot: Slot) -> None:
    """Tell every subscriber that a slot changed state (booked / reopened)."""
    socketio.emit("slot_update", slot.to_dict(), to=doctor_room_id(slot.doctor_id))


# --------------------------------------------------------------------------
# Client subscriptions (no sensitive data in these rooms, so any visitor
# may watch a doctor's public availability)
# --------------------------------------------------------------------------
@socketio.on("subscribe_doctor")
def on_subscribe_doctor(data):
    try:
        doctor_id = int((data or {}).get("doctor_id"))
    except (TypeError, ValueError):
        emit("error_event", {"error": "doctor_id must be an integer."})
        return
    join_room(doctor_room_id(doctor_id))
    emit("subscribed", {"room": doctor_room_id(doctor_id)})


@socketio.on("unsubscribe_doctor")
def on_unsubscribe_doctor(data):
    try:
        doctor_id = int((data or {}).get("doctor_id"))
    except (TypeError, ValueError):
        return
    leave_room(doctor_room_id(doctor_id))
