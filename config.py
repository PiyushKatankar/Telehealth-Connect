"""Application configuration.

All configuration is environment-driven so the same codebase can run on
SQLite (local quick start / CI) or PostgreSQL (production) without changes.
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent


class Config:
    """Base configuration shared by every environment."""

    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-insecure-secret-key-change-me")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    JSON_SORT_KEYS = False

    # Optional Redis/RabbitMQ URL. Needed ONLY when running Flask-SocketIO
    # with multiple worker processes (see README -> Deployment).
    SOCKETIO_MESSAGE_QUEUE = os.environ.get("SOCKETIO_MESSAGE_QUEUE")

    # Max length of the free-text symptom description sent with a booking.
    MAX_SYMPTOM_CHARS = 2000


class DevelopmentConfig(Config):
    DEBUG = True
    # Local quick start uses SQLite stored under instance/.
    # Point DATABASE_URL at PostgreSQL for a production-like setup.
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL",
        f"sqlite:///{BASE_DIR / 'instance' / 'telehealth.db'}",
    )


class TestingConfig(Config):
    TESTING = True
    SECRET_KEY = "test-secret-key"
    DEBUG = False


class ProductionConfig(Config):
    DEBUG = False
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL")


CONFIG_MAP = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
}


def get_config(name: str | None = None):
    """Return the config class for *name* (default: FLASK_CONFIG env var)."""
    name = (name or os.environ.get("FLASK_CONFIG", "development")).lower()
    return CONFIG_MAP.get(name, DevelopmentConfig)
