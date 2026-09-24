#!/bin/bash
set -e

python manage.py migrate --noinput

exec gunicorn mission_control.wsgi:application \
    --bind 0.0.0.0:8000 \
    --workers 2 \
    --timeout 120 \
    --access-logfile -
