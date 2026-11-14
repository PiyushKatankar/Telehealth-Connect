"""Role-based access control decorators."""
from functools import wraps

from flask import jsonify
from flask_login import current_user

from app.models import User


def login_required_api(view):
    """Require an authenticated user for a JSON API endpoint."""

    @wraps(view)
    def wrapped(*args, **kwargs):
        if not current_user.is_authenticated:
            return jsonify(error="Authentication required. Please log in."), 401
        return view(*args, **kwargs)

    return wrapped


def roles_required(*roles: str):
    """Require an authenticated user whose role is one of *roles*.

    Usage::

        @roles_required(User.ROLE_DOCTOR)
        def create_slot():
            ...
    """

    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if not current_user.is_authenticated:
                return jsonify(error="Authentication required. Please log in."), 401
            if current_user.role not in roles:
                allowed = " or ".join(roles)
                return (
                    jsonify(error=f"This action requires the '{allowed}' role."),
                    403,
                )
            return view(*args, **kwargs)

        return wrapped

    return decorator
