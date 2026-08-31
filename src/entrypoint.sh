#!/bin/bash
set -e

echo "Environment: ${ENVIRONMENT}"


if [ "$ENVIRONMENT" = "production" ] || [ "$ENVIRONMENT" = "staging" ]; then
    echo "Collecting static files..."
    python manage.py collectstatic --noinput
fi

# Run migrations
echo "Running migrations..."
python manage.py migrate --noinput


echo "Starting server..."
if [ "$ENVIRONMENT" = "production" ] || [ "$ENVIRONMENT" = "staging" ]; then
    python -m gunicorn --bind 0.0.0.0:8000 --workers 3 core.wsgi:application
else
    python manage.py runserver 0.0.0.0:8000
fi