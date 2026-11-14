"""Booking domain: doctors, slots, appointments (REST API)."""
from flask import Blueprint

booking_bp = Blueprint("booking", __name__)

from app.booking import routes  # noqa: E402,F401  (register routes on import)
