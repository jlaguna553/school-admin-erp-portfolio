#!/usr/bin/env bash
#
# Container entrypoint.
#
# Ordering here is not incidental -- django-tenants has a hard bootstrap
# sequence and getting it wrong leaves every URL returning 404:
#
#   1. wait for Postgres
#   2. migrate the *shared* apps into the public schema
#   3. ensure a Client row exists for schema "public" plus a Domain for the
#      request host  (TenantMainMiddleware 404s on an unknown host)
#   4. migrate the tenant schemas
#
set -euo pipefail

command="${1:-runserver}"
shift || true

DB_HOST="${DATABASE_HOST:-db}"
DB_PORT="${DATABASE_PORT:-5432}"
DB_USER="${POSTGRES_USER:-erp}"
DB_NAME="${POSTGRES_DB:-erp}"

log() { printf '\033[0;36m[entrypoint]\033[0m %s\n' "$*"; }

wait_for_postgres() {
  log "waiting for postgres at ${DB_HOST}:${DB_PORT}..."
  local attempts=0
  until pg_isready --host "$DB_HOST" --port "$DB_PORT" --username "$DB_USER" --dbname "$DB_NAME" >/dev/null 2>&1; do
    attempts=$((attempts + 1))
    if [ "$attempts" -ge 60 ]; then
      log "postgres did not become ready in time"
      exit 1
    fi
    sleep 1
  done
  log "postgres is ready"
}

bootstrap() {
  log "migrating shared apps (public schema)"
  python manage.py migrate_schemas --shared --noinput

  # The platform operator is created from configuration for the same reason the
  # demo school is: a free host has no shell, so `createsuperuser` can never be
  # run. Without this there is no account able to reach the operator console or
  # the Django admin, and the platform surfaces are unusable on a deployment
  # that otherwise looks healthy. `bootstrap_public` skips an email that already
  # exists, so this is safe on every boot.
  log "ensuring public tenant + domain"
  if [ -n "${PLATFORM_ADMIN_EMAIL:-}" ] && [ -n "${PLATFORM_ADMIN_PASSWORD:-}" ]; then
    python manage.py bootstrap_public \
      --domain "${PUBLIC_DOMAIN:-localhost}" \
      --email "${PLATFORM_ADMIN_EMAIL}" \
      --password "${PLATFORM_ADMIN_PASSWORD}"
  else
    python manage.py bootstrap_public --domain "${PUBLIC_DOMAIN:-localhost}"
  fi

  log "migrating tenant schemas"
  python manage.py migrate_schemas --tenant --noinput

  # Consolidate any school-local credential into a platform identity.
  #
  # Required, not optional: one hostname serves every school, so the login form
  # looks an address up platform-wide and a user who only exists inside a
  # schema is an account nobody can sign in to. A deployment that skipped this
  # would come up healthy with everyone locked out.
  #
  # Idempotent -- users already linked are skipped -- so it is safe on every
  # boot. It walks every user of every tenant, which is cheap at demo scale;
  # past a few thousand accounts, move it to a release step instead.
  #
  # It does not fail the boot when two schools hold the same address for
  # different people. That needs a human to decide which one keeps it, and
  # refusing to start would take the whole platform down for the rest.
  log "consolidating credentials into platform identities"
  python manage.py migrate_users_to_identities

  # Provision the demo school from configuration. Idempotent, because on hosts
  # with no shell this is the only opportunity to run it -- so it has to be safe
  # on every boot. Does nothing unless DEMO_SCHOOL_DOMAIN is set.
  log "provisioning demo tenant (if configured)"
  python manage.py provision_demo
}

# Migrating from the web process is convenient for a single container and wrong
# for more than one: replicas booting together race on the same DDL. Set
# RUN_MIGRATIONS_ON_START=false and run `docker-entrypoint.sh migrate` as a
# release/pre-deploy step instead.
maybe_bootstrap() {
  if [ "${RUN_MIGRATIONS_ON_START:-true}" = "true" ]; then
    bootstrap
  else
    log "skipping migrations (RUN_MIGRATIONS_ON_START=false)"
  fi
}

case "$command" in
  runserver)
    wait_for_postgres
    maybe_bootstrap
    log "starting development server on :8000"
    exec python manage.py runserver 0.0.0.0:8000
    ;;

  gunicorn)
    wait_for_postgres
    maybe_bootstrap
    log "starting gunicorn on :8000"
    exec gunicorn config.wsgi:application \
      --bind 0.0.0.0:8000 \
      --workers "${GUNICORN_WORKERS:-3}" \
      --timeout "${GUNICORN_TIMEOUT:-60}" \
      --access-logfile - \
      --error-logfile -
    ;;

  test)
    wait_for_postgres
    log "running pytest"
    exec pytest "$@"
    ;;

  migrate)
    wait_for_postgres
    bootstrap
    log "migrations complete"
    ;;

  manage)
    wait_for_postgres
    exec python manage.py "$@"
    ;;

  *)
    # Anything else is run verbatim, e.g. `docker compose run api bash`.
    exec "$command" "$@"
    ;;
esac
