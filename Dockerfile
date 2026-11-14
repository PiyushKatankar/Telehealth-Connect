FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

# -w 1: Socket.IO needs a message queue (SOCKETIO_MESSAGE_QUEUE) before
# scaling horizontally; keep a single worker for the demo deployment.
CMD ["gunicorn", "-b", "0.0.0.0:8000", "-w", "1", "-k", "eventlet", "wsgi:app"]
