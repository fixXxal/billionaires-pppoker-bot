web: python manage.py migrate && gunicorn billionaires_backend.wsgi:application
worker: python manage.py migrate && python bot.py
