"""Symptom chat: Socket.IO rooms per appointment + message history API."""
from flask import Blueprint

chat_bp = Blueprint("chat", __name__)

from app.chat import events, routes  # noqa: E402,F401
