"""Auth endpoints (JSON API + login/register HTML pages)."""
from flask import jsonify, render_template, request
from flask_login import current_user, login_user, logout_user
from sqlalchemy import select

from app.auth.decorators import login_required_api
from app.extensions import db, login_manager
from app.models import DoctorProfile, User

# The blueprint object is owned by app/auth/__init__.py — importing it here
# attaches every route below to the blueprint that the app registers.
from app.auth import auth_bp


@login_manager.user_loader
def load_user(user_id: str):
    return db.session.get(User, int(user_id))


# --------------------------------------------------------------------------
# HTML pages
# --------------------------------------------------------------------------
@auth_bp.get("/login")
def login_page():
    return render_template("login.html")


@auth_bp.get("/register")
def register_page():
    return render_template("register.html")


# --------------------------------------------------------------------------
# JSON API
# --------------------------------------------------------------------------
@auth_bp.post("/api/auth/register")
def api_register():
    data = request.get_json(silent=True) or {}

    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    full_name = (data.get("full_name") or "").strip()
    role = (data.get("role") or "").strip().lower()
    specialty = (data.get("specialty") or "").strip()
    bio = (data.get("bio") or "").strip()

    errors = []
    if "@" not in email or "." not in email or len(email) > 255:
        errors.append("A valid email address is required.")
    if len(password) < 8:
        errors.append("Password must be at least 8 characters.")
    if not (1 <= len(full_name) <= 120):
        errors.append("Full name is required (max 120 characters).")
    if role not in User.ROLES:
        errors.append("Role must be 'patient' or 'doctor'.")
    if role == User.ROLE_DOCTOR and not specialty:
        errors.append("Doctor accounts must include a specialty (e.g. Cardiology).")
    if errors:
        return jsonify(error="; ".join(errors)), 400

    if db.session.scalar(select(User).where(User.email == email)):
        return jsonify(error="An account with this email already exists."), 409

    user = User(email=email, full_name=full_name, role=role)
    user.set_password(password)
    db.session.add(user)
    db.session.flush()  # assign user.id before creating the profile

    if role == User.ROLE_DOCTOR:
        db.session.add(DoctorProfile(user_id=user.id, specialty=specialty, bio=bio))

    db.session.commit()
    return jsonify(user=user.public_dict()), 201


@auth_bp.post("/api/auth/login")
def api_login():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    user = db.session.scalar(select(User).where(User.email == email))
    if user is None or not user.check_password(password):
        return jsonify(error="Invalid email or password."), 401

    login_user(user, remember=True)
    return jsonify(user=user.public_dict())


@auth_bp.post("/api/auth/logout")
@login_required_api
def api_logout():
    logout_user()
    return jsonify(message="Logged out.")


@auth_bp.get("/api/auth/me")
@login_required_api
def api_me():
    me = current_user.public_dict()
    if current_user.doctor_profile:
        me["specialty"] = current_user.doctor_profile.specialty
        me["bio"] = current_user.doctor_profile.bio
    return jsonify(user=me)
