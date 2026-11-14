"""TeleHealth Connect — Flask + PostgreSQL + Socket.IO telehealth app."""
import os

from dotenv import load_dotenv
from flask import Flask, jsonify, request
from werkzeug.exceptions import HTTPException

load_dotenv()

from config import get_config  # noqa: E402


def _is_api_request() -> bool:
    return request.path.startswith("/api/")


def create_app(config_name: str | None = None) -> Flask:
    """Application factory.

    config_name: "development" | "testing" | "production"
                 (defaults to FLASK_CONFIG env var, then development)
    """
    app = Flask(__name__)
    config_cls = get_config(config_name)
    app.config.from_object(config_cls)

    # TestingConfig picks its DB URI at factory time so tests can inject a
    # per-test temp file database via TEST_DATABASE_URL.
    if config_cls.__name__ == "TestingConfig":
        app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get(
            "TEST_DATABASE_URL", "sqlite://"
        )
    elif app.config.get("SQLALCHEMY_DATABASE_URI") is None:
        raise RuntimeError("DATABASE_URL must be set in production.")

    # Ensure instance/ exists for the SQLite quick-start database.
    os.makedirs(app.instance_path, exist_ok=True)

    # --- blueprints & Socket.IO handlers (imported FIRST) ----------------
    # Socket.IO handlers registered with decorators must run BEFORE
    # socketio.init_app(): init_app builds a fresh server per app and only
    # replays handlers that were registered while no server existed yet.
    # Importing here makes tests (which create many apps per process) and
    # multi-instance deployments both work correctly.
    from app.auth import auth_bp  # noqa: F401 (imports auth routes)
    from app.booking import booking_bp  # noqa: F401
    from app.chat import chat_bp  # noqa: F401 (imports chat socket handlers)
    from app.main import main_bp  # noqa: F401
    from app import realtime  # noqa: F401 (registers availability socket handlers)

    # --- extensions -----------------------------------------------------
    from app.extensions import db, login_manager, socketio

    db.init_app(app)
    login_manager.init_app(app)
    socketio.init_app(app, message_queue=app.config.get("SOCKETIO_MESSAGE_QUEUE"))

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(booking_bp)
    app.register_blueprint(chat_bp)

    # --- error handlers -------------------------------------------------
    @app.errorhandler(HTTPException)
    def handle_http_exception(exc: HTTPException):
        if _is_api_request():
            return jsonify(error=exc.description), exc.code
        return exc

    @app.errorhandler(Exception)
    def handle_unexpected_error(exc: Exception):
        # Log full traceback server-side; clients only get a generic message.
        app.logger.exception("Unhandled error on %s %s", request.method, request.path)
        if _is_api_request():
            db.session.rollback()
            return jsonify(error="Internal server error."), 500
        raise exc

    @app.teardown_appcontext
    def _remove_session(_exc):
        """Flask-SQLAlchemy already handles session teardown; keep as explicit hook point."""
        pass

    return app
