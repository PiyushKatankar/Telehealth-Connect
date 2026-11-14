"""Shared Flask extension instances.

All extensions are created here (unbound) and bound to the app inside
``app.create_app``. This avoids circular imports between blueprints.
"""
from flask_login import LoginManager
from flask_socketio import SocketIO
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import event
from sqlalchemy.engine import Engine

db = SQLAlchemy()

# cors_allowed_origins="*" is fine for local development. In production set
# it to your real origin, e.g. SocketIO(cors_allowed_origins=["https://app.example.com"])
socketio = SocketIO(cors_allowed_origins="*", logger=False, engineio_logger=False)

login_manager = LoginManager()
login_manager.login_view = "auth.login_page"


@login_manager.unauthorized_handler
def _unauthorized():
    """API routes get JSON 401s; pages get redirected to the login form."""
    from flask import jsonify, redirect, request, url_for

    if request.path.startswith("/api/"):
        return jsonify(error="Authentication required. Please log in."), 401
    return redirect(url_for("auth.login_page", next=request.path))


@event.listens_for(Engine, "connect")
def _set_sqlite_pragmas(dbapi_connection, _connection_record):
    """Enable FK enforcement + busy timeout when running on SQLite (tests / quick start).

    PostgreSQL enforces foreign keys natively and uses row locks for
    concurrency; these pragmas make the SQLite fallback behave correctly.
    """
    if dbapi_connection.__class__.__module__.startswith("sqlite3"):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA busy_timeout=10000")
        cursor.close()
