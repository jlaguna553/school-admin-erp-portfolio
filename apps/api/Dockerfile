# syntax=docker/dockerfile:1

# ---------------------------------------------------------------------------
# Base: shared runtime for both targets.
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# gettext supplies msgfmt/xgettext so `makemessages` and `compilemessages` work
# inside the container even when the host has no GNU gettext installed.
# postgresql-client gives the entrypoint a real readiness probe (pg_isready).
RUN apt-get update \
    && apt-get install --no-install-recommends -y \
        gettext \
        postgresql-client \
        curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Run as a non-root user. Created here so both targets inherit it.
RUN useradd --create-home --uid 1000 app

# ---------------------------------------------------------------------------
# Dependencies: a separate layer so code edits do not reinstall packages.
# ---------------------------------------------------------------------------
FROM base AS deps

COPY requirements/ /app/requirements/

# ---------------------------------------------------------------------------
# Development: hot reload, dev tooling, source mounted over /app by compose.
# ---------------------------------------------------------------------------
FROM deps AS dev

RUN pip install -r requirements/dev.txt

ENV DJANGO_SETTINGS_MODULE=config.settings.dev

COPY --chown=app:app . /app/
RUN chmod +x /app/scripts/docker-entrypoint.sh

USER app
EXPOSE 8000

# Invoked through bash rather than relying on the executable bit: in the dev
# target compose bind-mounts the host source over /app, which replaces the
# chmod'd copy with whatever permissions the host file happens to have.
ENTRYPOINT ["bash", "/app/scripts/docker-entrypoint.sh"]
CMD ["runserver"]

# ---------------------------------------------------------------------------
# Production: gunicorn, no dev dependencies, assets collected at build time.
# ---------------------------------------------------------------------------
FROM deps AS prod

RUN pip install -r requirements/prod.txt

ENV DJANGO_SETTINGS_MODULE=config.settings.prod

COPY --chown=app:app . /app/
RUN chmod +x /app/scripts/docker-entrypoint.sh

# Build-time management commands read settings, and prod.py deliberately has no
# defaults for its secrets -- it must fail loudly at boot rather than start
# insecurely. Neither command connects to a database or bakes these values into
# the image, so throwaway values are supplied here purely to let settings load.
#
# compilemessages: gettext is installed in this image, so the canonical Django
# command is used rather than the pure-Python fallback that exists for hosts
# without the GNU tooling.
RUN DJANGO_SECRET_KEY=build-only-not-used-at-runtime \
    DJANGO_ALLOWED_HOSTS=localhost \
    CORS_ALLOWED_ORIGINS=http://localhost \
    python manage.py compilemessages --ignore=.venv \
 && DJANGO_SECRET_KEY=build-only-not-used-at-runtime \
    DJANGO_ALLOWED_HOSTS=localhost \
    CORS_ALLOWED_ORIGINS=http://localhost \
    python manage.py collectstatic --noinput --clear

USER app
EXPOSE 8000

# Invoked through bash rather than relying on the executable bit: in the dev
# target compose bind-mounts the host source over /app, which replaces the
# chmod'd copy with whatever permissions the host file happens to have.
ENTRYPOINT ["bash", "/app/scripts/docker-entrypoint.sh"]
CMD ["gunicorn"]
