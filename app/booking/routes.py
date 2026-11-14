"""Booking REST API.

Endpoints
---------
GET    /api/doctors                     list doctors + open-slot counts
GET    /api/doctors/<id>/slots          a doctor's future open slots
POST   /api/slots                       doctor: create availability
DELETE /api/slots/<id>                  doctor: remove own open slot
POST   /api/appointments                patient: book a slot (transactional)
GET    /api/appointments                role-aware list of my appointments
POST   /api/appointments/<id>/cancel    participant: cancel
"""
from datetime import datetime, timedelta, timezone

from flask import current_app, jsonify, request
from flask_login import current_user, login_required
from sqlalchemy import func, select

from app.auth.decorators import login_required_api, roles_required
from app.booking.service import book_slot, cancel_appointment
from app.extensions import db
from app.models import Appointment, DoctorProfile, Slot, User, utc_now

# The blueprint object is owned by app/booking/__init__.py.
from app.booking import booking_bp


def _parse_iso_datetime(value: str) -> datetime | None:
    """Parse an ISO-8601 datetime; normalize to naive UTC for storage."""
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


# --------------------------------------------------------------------------
# Doctors
# --------------------------------------------------------------------------
@booking_bp.get("/api/doctors")
def api_list_doctors():
    """Public directory of doctors with their upcoming open-slot counts."""
    doctors = db.session.execute(
        select(User, DoctorProfile)
        .join(DoctorProfile, DoctorProfile.user_id == User.id)
        .where(User.role == User.ROLE_DOCTOR)
        .order_by(User.full_name)
    ).all()

    open_counts = dict(
        db.session.execute(
            select(Slot.doctor_id, func.count(Slot.id))
            .where(Slot.status == Slot.STATUS_OPEN, Slot.start_time >= utc_now())
            .group_by(Slot.doctor_id)
        ).all()
    )

    return jsonify(
        doctors=[
            {
                "id": user.id,
                "full_name": user.full_name,
                "specialty": profile.specialty,
                "bio": profile.bio,
                "open_slots": open_counts.get(user.id, 0),
            }
            for user, profile in doctors
        ]
    )


@booking_bp.get("/api/doctors/<int:doctor_id>/slots")
def api_doctor_slots(doctor_id: int):
    """Future open slots of one doctor (what the booking grid renders)."""
    if not db.session.get(User, doctor_id):
        return jsonify(error="Doctor not found."), 404

    slots = db.session.scalars(
        select(Slot)
        .where(
            Slot.doctor_id == doctor_id,
            Slot.status == Slot.STATUS_OPEN,
            Slot.start_time >= utc_now(),
        )
        .order_by(Slot.start_time)
        .limit(200)
    ).all()
    return jsonify(slots=[s.to_dict() for s in slots])


# --------------------------------------------------------------------------
# Slot management (doctors)
# --------------------------------------------------------------------------
@booking_bp.post("/api/slots")
@roles_required(User.ROLE_DOCTOR)
def api_create_slot():
    """Create one availability slot. Overlaps with existing slots are rejected."""
    data = request.get_json(silent=True) or {}
    start = _parse_iso_datetime(data.get("start_time") or "")
    end = _parse_iso_datetime(data.get("end_time") or "")
    if start is None or end is None:
        return jsonify(error="start_time and end_time must be ISO-8601 datetimes."), 400

    if start < utc_now():
        return jsonify(error="Slot must start in the future."), 400
    if end <= start:
        return jsonify(error="end_time must be after start_time."), 400
    if end - start > timedelta(hours=8):
        return jsonify(error="A slot may be at most 8 hours long."), 400

    overlap = db.session.scalar(
        select(func.count(Slot.id)).where(
            Slot.doctor_id == current_user.id,
            Slot.start_time < end,
            Slot.end_time > start,
        )
    )
    if overlap:
        return jsonify(error="This slot overlaps another slot you already offer."), 409

    slot = Slot(doctor_id=current_user.id, start_time=start, end_time=end)
    db.session.add(slot)
    db.session.commit()
    return jsonify(slot=slot.to_dict()), 201


@booking_bp.delete("/api/slots/<int:slot_id>")
@roles_required(User.ROLE_DOCTOR)
def api_delete_slot(slot_id: int):
    """Remove one of my own slots (only while it is still open)."""
    slot = db.session.get(Slot, slot_id)
    if slot is None or slot.doctor_id != current_user.id:
        return jsonify(error="Slot not found."), 404
    if slot.status != Slot.STATUS_OPEN:
        return jsonify(error="Booked slots cannot be deleted; cancel the appointment instead."), 409

    db.session.delete(slot)
    db.session.commit()
    return jsonify(message="Slot removed.")


# --------------------------------------------------------------------------
# Appointments (patients book; both sides view/cancel)
# --------------------------------------------------------------------------
@booking_bp.post("/api/appointments")
@login_required_api
def api_book_appointment():
    data = request.get_json(silent=True) or {}
    try:
        slot_id = int(data.get("slot_id"))
    except (TypeError, ValueError):
        return jsonify(error="slot_id (integer) is required."), 400

    symptoms = (data.get("symptoms") or "").strip()
    max_chars = current_app.config["MAX_SYMPTOM_CHARS"]
    if len(symptoms) > max_chars:
        return jsonify(error=f"Symptoms description is limited to {max_chars} characters."), 400

    appointment, error = book_slot(current_user, slot_id, symptoms)
    if error:
        status, message = error
        return jsonify(error=message), status

    return jsonify(appointment=appointment.to_dict()), 201


@booking_bp.get("/api/appointments")
@login_required_api
def api_list_appointments():
    """Patients see their bookings; doctors see their schedule."""
    scope = (
        Appointment.doctor_id if current_user.role == User.ROLE_DOCTOR
        else Appointment.patient_id
    )
    appointments = db.session.scalars(
        select(Appointment)
        .where(scope == current_user.id)
        .order_by(Appointment.created_at.desc())
        .limit(200)
    ).all()
    return jsonify(appointments=[a.to_dict() for a in appointments])


@booking_bp.post("/api/appointments/<int:appointment_id>/cancel")
@login_required
def api_cancel_appointment(appointment_id: int):
    appointment, error = cancel_appointment(current_user, appointment_id)
    if error:
        status, message = error
        return jsonify(error=message), status
    return jsonify(appointment=appointment.to_dict())
