#!/usr/bin/env sh
set -e

DB_PATH="${DATABASE_PATH:-/app/banos.db}"

if [ ! -f "$DB_PATH" ]; then
  echo ">> No existe $DB_PATH. Sembrando base..."
  python seed.py
else
  echo ">> BD existente: $DB_PATH"
fi

exec "$@"
