"""One-command database setup + demo data for TeleHealth Connect.

    python seed.py

Creates all tables (works on both SQLite and PostgreSQL) and, if the
database is empty, inserts three demo doctors with a week of availability
plus one demo patient. Safe to run more than once.
"""
from datetime import timedelta

from app import create_app
from app.extensions import db
from app.models import DoctorProfile, Slot, User, utc_now

DEMO_DOCTORS = [
    ("doctor.aisha@clinic.test", "Doctor#123", "Dr. Aisha Rahman", "Cardiology",
     "Heart health, hypertension and preventive cardiology."),
    ("doctor.daniel@clinic.test", "Doctor#123", "Dr. Daniel Kim", "Dermatology",
     "Skin, hair and nail conditions, allergic reactions."),
    ("doctor.elena@clinic.test", "Doctor#123", "Dr. Elena Petrova", "Pediatrics",
     "Child health from newborn through teenage years."),
]

DEMO_PATIENT = ("patient@clinic.test", "Patient#123", "Sam Patient")

DAYS_AHEAD = 7       # seed availability for the next 7 days
FIRST_HOUR_UTC = 9   # first slot at 09:00 UTC
LAST_HOUR_UTC = 16   # last slot starts 16:00 UTC
SLOT_MINUTES = 30


def seed() -> None:
    app = create_app()
    with app.app_context():
        db.create_all()

        already = db.session.query(User).filter_by(role=User.ROLE_DOCTOR).count()
        if already:
            print("Database already seeded — nothing to do.")
            return

        # Demo doctors + one week of 30-minute slots each day.
        tomorrow = (utc_now() + timedelta(days=1)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        for email, password, name, specialty, bio in DEMO_DOCTORS:
            user = User(email=email, full_name=name, role=User.ROLE_DOCTOR)
            user.set_password(password)
            db.session.add(user)
            db.session.flush()  # get user.id for the profile + slots

            db.session.add(DoctorProfile(user_id=user.id, specialty=specialty, bio=bio))
            for day in range(DAYS_AHEAD):
                for hour in range(FIRST_HOUR_UTC, LAST_HOUR_UTC + 1):
                    start = tomorrow + timedelta(days=day, hours=hour)
                    db.session.add(
                        Slot(
                            doctor_id=user.id,
                            start_time=start,
                            end_time=start + timedelta(minutes=SLOT_MINUTES),
                        )
                    )

        patient = User(email=DEMO_PATIENT[0], full_name=DEMO_PATIENT[2], role=User.ROLE_PATIENT)
        patient.set_password(DEMO_PATIENT[1])
        db.session.add(patient)

        db.session.commit()
        print("Seeded demo accounts and 7 days of availability:")
        print(f"  patient : {DEMO_PATIENT[0]:<28} / {DEMO_PATIENT[1]}")
        for email, _pw, name, specialty, _bio in DEMO_DOCTORS:
            print(f"  doctor  : {email:<28} / Doctor#123   ({name}, {specialty})")


if __name__ == "__main__":
    seed()
