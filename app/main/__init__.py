"""Main pages: landing page, booking UI, dashboard, health check."""
from flask import Blueprint, jsonify, render_template
from flask_login import current_user, login_required

main_bp = Blueprint("main", __name__)


@main_bp.get("/")
def index():
    return render_template("index.html")


@main_bp.get("/booking")
def booking_page():
    return render_template("booking.html")


@main_bp.get("/dashboard")
@login_required
def dashboard():
    return render_template("dashboard.html")


@main_bp.get("/healthz")
def healthz():
    """Liveness probe used by load balancers / container orchestrators."""
    return jsonify(status="ok")
