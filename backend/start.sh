#!/usr/bin/env bash
# Exit on error
set -o errexit

echo "Initializing database..."
python manage.py migrate
python manage.py seed_data
python manage.py setup_schedules

echo "Starting Django-Q background worker..."
# Start the background worker process with & so it runs in the background
python manage.py qcluster &

echo "Starting Django API server..."
# Start gunicorn in the foreground. This binds to the port Render expects.
exec gunicorn config.wsgi:application --bind 0.0.0.0:$PORT --workers 2 --timeout 120
