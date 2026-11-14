"""Production WSGI entry point.

    gunicorn -b 0.0.0.0:8000 -w 1 -k eventlet wsgi:app

Important: keep ONE worker unless you configure a message queue
(SOCKETIO_MESSAGE_QUEUE=redis://...), otherwise Socket.IO clients connected
to different workers will not see each other's events.
"""
from dotenv import load_dotenv

load_dotenv()

from app import create_app  # noqa: E402  (needs dotenv loaded first)

app = create_app("production")

if __name__ == "__main__":
    from app.extensions import socketio

    socketio.run(app, host="0.0.0.0", port=8000)
