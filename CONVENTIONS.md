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
  `organization` (volunteers, groups, Discord services), `AktivitetsTeam`, `Butikken`, `Depot`, `Foto`, `Loeb`, `Sjak`, `SOS`, `Teknik`, `Wiki`, `emailing`,
  `notifications` (PWA manifest/service worker, Web Push subscriptions, push preferences and token-protected iCalendar feeds)
- Shared helpers in `src/utils/`; global templates in `src/templates/`

## Patterns
- Service-layer modules for heavy logic (e.g. `emailing/services.py`, `organization/discord_services.py`); keep views thin
- DRF serializers + `api.py` for API endpoints
- Side effects via Django signals (`signals.py`) and Celery tasks
- Model changes require migrations in the app's `migrations/`

### Shared UI modules
Booking and catalog pages share a set of template components and view mixins. Prefer extending/reusing these over copying markup into an app template:

- `src/templates/components/booking_list.html` – Sjak-style booking list (used by Sjak, Teknik, Depot, Foto, SOS, Butikken, AktivitetsTeam "mine" and Legeaftaler)
- `src/templates/components/booking_detail.html` – Sjak-style booking detail page with blocks for app-specific information, actions and scripts (used by all booking modules)
- `src/templates/components/booking_form.html` – shared booking form layout with blocks for app-specific fields/scripts
- `src/templates/components/item_list_table.html` – Depot-style searchable item table (Sjak, Foto, SOS, Butikken, Depot)
- `src/templates/components/item_list_gallery.html` – card gallery for item catalogs (Teknik, AktivitetsTeam)
- `src/templates/components/item_detail.html` – shared catalog item detail page with blocks for app-specific alerts, metadata, extras and sidebar content (used by all item catalogs)
- `src/templates/components/booking_status_badge.html` and `pagination.html` – small shared partials
- `src/utils/ui.py` – `BookingListContextMixin`, `BookingDetailContextMixin`, `ItemListContextMixin`, `ItemDetailContextMixin` and `ItemGalleryContextMixin`, which supply the component labels/URL names from each view

## Coding Style
- PEP 8, type hints on new/changed functions
- Templates linted with djlint
- Config from environment variables (`.env*`); never commit secrets
- Tests live in `tests.py` or `tests/` per app; run with `python src/manage.py test`
