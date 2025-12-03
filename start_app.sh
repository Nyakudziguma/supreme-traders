venv/bin/gunicorn --access-logfile - --workers 1 --bind 0.0.0.0:8025 supreme.wsgi:application

