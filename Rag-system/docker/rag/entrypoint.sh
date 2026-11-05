#!/bin/bash
set -e

# Ensure asset directories exist (works with mounted volumes)
mkdir -p /app/assets/files \
         /app/assets/database \
         /app/assets/database/excel \
         /app/assets/database/sql

echo "Running database migrations..."
cd /app/models/db_schemes/ragsystem/
alembic upgrade head
cd /app

echo "Starting application..."
exec "$@"