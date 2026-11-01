# Project Conventions

## Stack
- Django 5.2 + Django REST Framework, Python (virtualenv in `venv/`)
- PostgreSQL 17 in Docker (SQLite fallback for local dev), Redis 7 (cache, Constance backend, Celery broker)
- Celery for async tasks (`src/core/celery.py`, `emailing/tasks.py`, `organization/tasks.py`)
- Admin UI: django-unfold, django-import-export, django-simple-history
- Frontend: server-rendered templates, bootstrap5, tiptap editor
- Email via Amazon SES (django-ses); settings toggles via django-constance
- Served by gunicorn behind nginx (certbot for TLS); docker-compose for dev/staging/prod

## Layout
- Project root: `docker-compose*.yaml`, `dockerfile`, `nginx/`, `scripts/`
- Django project in `src/`; settings/urls/celery in `src/core/`
- Apps (each typically has `models.py`, `views.py`, `forms.py`, `serializers.py`, `api.py`, `urls.py`, `signals.py`, `admin.py`, `templates/`):
  `organization` (volunteers, groups, Discord services), `AktivitetsTeam`, `Butikken`, `Depot`, `Foto`, `Loeb`, `Sjak`, `SOS`, `Teknik`, `emailing`
- Shared helpers in `src/utils/`; global templates in `src/templates/`

## Patterns
- Service-layer modules for heavy logic (e.g. `emailing/services.py`, `organization/discord_services.py`); keep views thin
- DRF serializers + `api.py` for API endpoints
- Side effects via Django signals (`signals.py`) and Celery tasks
- Model changes require migrations in the app's `migrations/`

## Coding Style
- PEP 8, type hints on new/changed functions
- Templates linted with djlint
- Config from environment variables (`.env*`); never commit secrets
- Tests live in `tests.py` or `tests/` per app; run with `python src/manage.py test`
