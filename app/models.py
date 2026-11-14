"""Database models.

Schema design notes (double-booking prevention lives in both layers):

1. Application layer: the booking service runs
   ``SELECT ... FOR UPDATE`` on the slot row, so concurrent transactions
   serialize on that row under PostgreSQL.
2. Database layer: ``Appointment.slot_id`` has a UNIQUE constraint, so a
   slot can only ever appear in one appointment, and ``Slot`` has a UNIQUE
   ``(doctor_id, start_time)`` index so a doctor can never be given two
   overlapping-by-start slots. Even if two requests raced past the row
   lock (e.g. on backends without FOR UPDATE, such as the SQLite quick
   start), the second ``INSERT`` fails and is converted to a HTTP 409.

All datetimes are stored as **naive UTC**; JSON serialization appends a
``Z`` suffix so browser-side ``new Date(...)`` converts to local time.
"""
from datetime import datetime, timezone

from flask_login import UserMixin
from sqlalchemy import text as sa_text
from werkzeug.security import check_password_hash, generate_password_hash

from app.extensions import db


def utc_now() -> datetime:
    """Naive-UTC 'now' — the single source of time in this app."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _iso_utc(dt: datetime | None) -> str | None:
    """Serialize a naive-UTC datetime with a 'Z' suffix for JSON."""
    return dt.isoformat(timespec="seconds") + "Z" if dt else None


class User(UserMixin, db.Model):
    """Account for either a patient or a doctor (role-based)."""

    __tablename__ = "users"

    ROLE_PATIENT = "patient"
    ROLE_DOCTOR = "doctor"
    ROLES = (ROLE_PATIENT, ROLE_DOCTOR)

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    full_name = db.Column(db.String(120), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # 'patient' | 'doctor'
    created_at = db.Column(db.DateTime, nullable=False, default=utc_now)

    # One-to-one doctor profile (NULL for patients)
    doctor_profile = db.relationship(
        "DoctorProfile", back_populates="user", uselist=False, cascade="all, delete-orphan"
    )

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    @property
    def is_doctor(self) -> bool:
        return self.role == self.ROLE_DOCTOR

    def public_dict(self) -> dict:
        return {"id": self.id, "email": self.email, "full_name": self.full_name, "role": self.role}

    def __repr__(self) -> str:  # pragma: no cover
        return f"<User {self.id} {self.role} {self.email}>"


class DoctorProfile(db.Model):
    """Extra clinical info that only doctors have."""

    __tablename__ = "doctor_profiles"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    specialty = db.Column(db.String(120), nullable=False)
    bio = db.Column(db.Text, nullable=False, server_default="")

    user = db.relationship("User", back_populates="doctor_profile")

    def public_dict(self) -> dict:
        data = self.user.public_dict()
        data.update(specialty=self.specialty, bio=self.bio)
        return data


class Slot(db.Model):
    """A bookable time window offered by a doctor."""

    __tablename__ = "slots"
    __table_args__ = (
        db.UniqueConstraint("doctor_id", "start_time", name="uq_slot_doctor_start"),
        db.Index("ix_slot_doctor_status_start", "doctor_id", "status", "start_time"),
    )

    STATUS_OPEN = "open"
    STATUS_BOOKED = "booked"

    id = db.Column(db.Integer, primary_key=True)
    doctor_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    start_time = db.Column(db.DateTime, nullable=False)
    end_time = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.String(20), nullable=False, default=STATUS_OPEN)
    created_at = db.Column(db.DateTime, nullable=False, default=utc_now)

    doctor = db.relationship("User", foreign_keys=[doctor_id])
    appointment = db.relationship(
        "Appointment", back_populates="slot", uselist=False, cascade="all, delete-orphan"
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "doctor_id": self.doctor_id,
            "start_time": _iso_utc(self.start_time),
            "end_time": _iso_utc(self.end_time),
            "status": self.status,
        }

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Slot {self.id} doctor={self.doctor_id} {self.start_time} {self.status}>"


class Appointment(db.Model):
    """A booking: links one patient, one doctor and exactly one slot."""

    __tablename__ = "appointments"
    __table_args__ = (
        # THE anti-double-booking guarantee at the schema level: a slot can
        # have at most one ACTIVE (non-cancelled) appointment. The partial
        # WHERE clause works on both SQLite and PostgreSQL, so cancelling an
        # appointment frees its slot for rebooking.
        db.Index(
            "uq_appointment_active_slot",
            "slot_id",
            unique=True,
            sqlite_where=sa_text("status != 'cancelled'"),
            postgresql_where=sa_text("status != 'cancelled'"),
        ),
        db.Index("ix_appointment_patient", "patient_id"),
        db.Index("ix_appointment_doctor", "doctor_id"),
    )

    STATUS_SCHEDULED = "scheduled"
    STATUS_CANCELLED = "cancelled"
    STATUS_COMPLETED = "completed"

    id = db.Column(db.Integer, primary_key=True)
    slot_id = db.Column(
        db.Integer, db.ForeignKey("slots.id", ondelete="CASCADE"), nullable=False, index=True
    )
    patient_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    doctor_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    symptoms = db.Column(db.Text, nullable=False, server_default="")
    status = db.Column(db.String(20), nullable=False, default=STATUS_SCHEDULED)
    created_at = db.Column(db.DateTime, nullable=False, default=utc_now)

    slot = db.relationship("Slot", back_populates="appointment")
    patient = db.relationship("User", foreign_keys=[patient_id])
    doctor = db.relationship("User", foreign_keys=[doctor_id])
    messages = db.relationship(
        "Message", back_populates="appointment", order_by="Message.created_at"
    )

    def involves(self, user) -> bool:
        return user.id in (self.patient_id, self.doctor_id)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "status": self.status,
            "symptoms": self.symptoms,
            "created_at": _iso_utc(self.created_at),
            "slot": self.slot.to_dict() if self.slot else None,
            "patient": {"id": self.patient.id, "full_name": self.patient.full_name},
            "doctor": {
                "id": self.doctor.id,
                "full_name": self.doctor.full_name,
                "specialty": self.doctor.doctor_profile.specialty
                if self.doctor.doctor_profile
                else None,
            },
        }


class Message(db.Model):
    """One chat message inside an appointment's symptom chat."""

    __tablename__ = "messages"
    __table_args__ = (db.Index("ix_message_appointment_time", "appointment_id", "created_at"),)

    MAX_BODY_CHARS = 2000

    id = db.Column(db.Integer, primary_key=True)
    appointment_id = db.Column(
        db.Integer, db.ForeignKey("appointments.id", ondelete="CASCADE"), nullable=False
    )
    sender_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    body = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=utc_now)

    appointment = db.relationship("Appointment", back_populates="messages")
    sender = db.relationship("User")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "appointment_id": self.appointment_id,
            "sender_id": self.sender_id,
            "sender_name": self.sender.full_name if self.sender else None,
            "sender_role": self.sender.role if self.sender else None,
            "body": self.body,
            "created_at": _iso_utc(self.created_at),
        }
