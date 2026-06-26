#!/bin/sh
set -e

# Run DB migrations before starting the app, so a fresh `docker compose up`
# bootstraps the schema automatically.
alembic upgrade head

exec uvicorn app.main:app --host 0.0.0.0 --port 8000