"""Socket.IO event handlers for the appointment symptom chat.

Auth model: Flask-SocketIO shares the Flask session, so a socket connection
from a browser is already identified by ``current_user``. Every event
re-checks authentication and that the user is a participant of the
appointment before joining the room or persisting a message.
"""
from flask_login import current_user
from flask_socketio import emit, join_room, leave_room

from app.extensions import db, socketio
from app.models import Appointment, Message
from app.realtime import appointment_room_id


def _authorized(appointment_id: int) -> Appointment | None:
    """Return the appointment if the current user may see its chat, else None."""
    if not current_user.is_authenticated:
        return None
    appointment = db.session.get(Appointment, appointment_id)
    if appointment is None or not appointment.involves(current_user):
        return None
    return appointment


@socketio.on("join_chat")
def on_join_chat(data):
    appointment = _authorized((data or {}).get("appointment_id"))
    if appointment is None:
        emit("chat_error", {"error": "You are not a participant of this appointment."})
        return

    room = appointment_room_id(appointment.id)
    join_room(room)

    # History replay goes only to the joining client.
    from sqlalchemy import select

    history = db.session.scalars(
        select(Message).where(Message.appointment_id == appointment.id).limit(200)
    ).all()

    emit(
        "chat_joined",
        {
            "appointment_id": appointment.id,
            "history": [m.to_dict() for m in history],
        },
    )


@socketio.on("send_message")
def on_send_message(data):
    data = data or {}
    appointment = _authorized(data.get("appointment_id"))
    if appointment is None:
        emit("chat_error", {"error": "You are not a participant of this appointment."})
        return

    body = (data.get("body") or "").strip()
    if not body:
        emit("chat_error", {"error": "Message cannot be empty."})
        return
    if len(body) > Message.MAX_BODY_CHARS:
        emit("chat_error", {"error": f"Message is limited to {Message.MAX_BODY_CHARS} characters."})
        return

    message = Message(appointment_id=appointment.id, sender_id=current_user.id, body=body)
    db.session.add(message)
    db.session.commit()

    # Everyone in the room (patient + doctor) sees the message.
    socketio.emit("chat_message", message.to_dict(), to=appointment_room_id(appointment.id))


@socketio.on("leave_chat")
def on_leave_chat(data):
    appointment = _authorized((data or {}).get("appointment_id"))
    if appointment is None:
        return
    leave_room(appointment_room_id(appointment.id))
    emit("chat_left", {"appointment_id": appointment.id})
