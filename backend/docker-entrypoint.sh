#!/bin/sh
# Apply pending migrations before the server (or any other command) starts.
# The app lifespan would do this too, but doing it here fails fast with a
# readable log line and keeps the seed script and one-off commands consistent.
# SQLite databases are created by the app itself (create_all), so skip them.
set -eu

case "${DATABASE_URL:-sqlite}" in
  sqlite*) ;;
  *) echo "Applying database migrations..." && alembic upgrade head ;;
esac

exec "$@"
