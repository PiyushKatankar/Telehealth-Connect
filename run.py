"""Development entry point.

    python run.py          -> http://127.0.0.1:5000

For production use gunicorn with the eventlet worker (see wsgi.py and the
README's Deployment section); run.py only wires the dev server.
"""
import os

from dotenv import load_dotenv

load_dotenv()

from app import create_app  # noqa: E402  (needs dotenv loaded first)
from app.extensions import socketio  # noqa: E402

app = create_app()

if __name__ == "__main__":
    socketio.run(
        app,
        host=os.environ.get("HOST", "127.0.0.1"),
        port=int(os.environ.get("PORT", "5000")),
        debug=app.config.get("DEBUG", False),
        # Dev-only flag: Werkzeug is safe for local development but must not
        # serve production traffic (use gunicorn -k eventlet wsgi:app).
        allow_unsafe_werkzeug=True,
    )
