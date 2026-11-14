"""Chat HTTP routes: the chat page + REST message history."""
from flask import abort, jsonify, render_template
from flask_login import current_user, login_required
from sqlalchemy import select

from app.chat.events import _authorized
from app.extensions import db
from app.models import Message

# The blueprint object is owned by app/chat/__init__.py.
from app.chat import chat_bp


@chat_bp.get("/chat/<int:appointment_id>")
@login_required
def chat_page(appointment_id: int):
    appointment = _authorized(appointment_id)
    if appointment is None:
        abort(403, description="You are not a participant of this appointment.")
    return render_template("chat.html", appointment=appointment)


@chat_bp.get("/api/appointments/<int:appointment_id>/messages")
@login_required
def api_message_history(appointment_id: int):
    appointment = _authorized(appointment_id)
    if appointment is None:
        return jsonify(error="You are not a participant of this appointment."), 403

    messages = db.session.scalars(
        select(Message)
        .where(Message.appointment_id == appointment_id)
        .order_by(Message.created_at, Message.id)
        .limit(500)
    ).all()
    return jsonify(messages=[m.to_dict() for m in messages])
