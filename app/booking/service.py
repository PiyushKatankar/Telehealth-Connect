"""Booking services.

This module owns the **transaction-safe booking logic**:

    BEGIN;
        SELECT * FROM slots WHERE id = :slot_id FOR UPDATE;  -- row lock
        -- status still 'open'? in the future?
        UPDATE slots SET status = 'booked' WHERE id = :slot_id;
        INSERT INTO appointments (slot_id, ...) VALUES (...);
    COMMIT;

Under PostgreSQL the FOR UPDATE row lock serializes concurrent booking
attempts for the same slot: the first transaction wins, the second sees
``status = 'booked'`` and is rejected with HTTP 409 before any write.

Defense in depth: ``appointments.slot_id`` carries a UNIQUE constraint, so
even on backends without FOR UPDATE (the SQLite quick start) or under any
application bug, the database itself refuses the second appointment for a
slot — the violating INSERT raises IntegrityError, we roll back and
surface 409.
"""
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models import Appointment, Slot, User, utc_now
from app.realtime import broadcast_slot_update

MAX_SYMPTOM_CHARS = 2000


def book_slot(patient: User, slot_id: int, symptoms: str | None = None):
    """Atomically book *slot_id* for *patient*.

    Returns ``(appointment, None)`` on success or ``(None, (http_status,
    error_message))`` on failure. All checks happen inside the locked
    transaction; commit is the single success point.
    """
    now = utc_now()

    # 1. Lock the slot row (no-op lock on SQLite; FOR UPDATE on PostgreSQL).
    slot = db.session.execute(
        select(Slot).where(Slot.id == slot_id).with_for_update()
    ).scalar_one_or_none()

    if slot is None:
        return None, (404, "Slot not found.")
    if slot.status != Slot.STATUS_OPEN:
        return None, (409, "This slot has just been taken. Please pick another one.")
    if slot.start_time < now:
        return None, (409, "This slot is in the past and cannot be booked.")

    # 2. Reserve it: mark booked + create the appointment in ONE transaction.
    slot.status = Slot.STATUS_BOOKED
    appointment = Appointment(
        slot_id=slot.id,
        patient_id=patient.id,
        doctor_id=slot.doctor_id,
        symptoms=(symptoms or "").strip()[:MAX_SYMPTOM_CHARS],
    )
    db.session.add(appointment)

    # 3. Commit is the atomic switch. The unique constraint on slot_id is
    #    the final arbiter against double-booking.
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return None, (409, "This slot has just been taken. Please pick another one.")

    # 4. Push the new state to everyone watching this doctor's calendar.
    broadcast_slot_update(slot)
    return appointment, None


def cancel_appointment(user: User, appointment_id: int):
    """Cancel an appointment (patient or doctor side) and reopen the slot."""
    appointment = db.session.get(Appointment, appointment_id)
    if appointment is None:
        return None, (404, "Appointment not found.")

    # Only the two participants may act on an appointment.
    if not appointment.involves(user):
        return None, (404, "Appointment not found.")  # don't leak others' ids

    if appointment.status == Appointment.STATUS_CANCELLED:
        return None, (409, "Appointment is already cancelled.")

    appointment.status = Appointment.STATUS_CANCELLED

    # Future slots become bookable again; past slots just stay closed.
    if appointment.slot and appointment.slot.start_time >= utc_now():
        appointment.slot.status = Slot.STATUS_OPEN

    db.session.commit()
    if appointment.slot:
        broadcast_slot_update(appointment.slot)
    return appointment, None
