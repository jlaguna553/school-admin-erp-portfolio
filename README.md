# School Administration ERP

![Python](https://img.shields.io/badge/Python%203.12-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Django](https://img.shields.io/badge/Django%205.1-092E20?style=for-the-badge&logo=django&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL%2016-4169E1?style=for-the-badge&logo=postgresql&logoColor=white)
![Next.js](https://img.shields.io/badge/Next.js%2015-000000?style=for-the-badge&logo=nextdotjs&logoColor=white)
![TypeScript](https://img.shields.io/badge/TypeScript-3178C6?style=for-the-badge&logo=typescript&logoColor=white)
![Tailwind](https://img.shields.io/badge/Tailwind%20v4-06B6D4?style=for-the-badge&logo=tailwindcss&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-2496ED?style=for-the-badge&logo=docker&logoColor=white)
![Turborepo](https://img.shields.io/badge/Turborepo-EF4444?style=for-the-badge&logo=turborepo&logoColor=white)
![pytest](https://img.shields.io/badge/pytest-0A9EDC?style=for-the-badge&logo=pytest&logoColor=white)
![Playwright](https://img.shields.io/badge/Playwright-2EAD33?style=for-the-badge&logo=playwright&logoColor=white)

Multi-institution (multitenant), internationalized (`es` / `en`) ERP for
educational institutions. A **layered modular monolith** built so individual
modules can be extracted into services later without a schema migration.

- **Backend** — Python 3.12 · Django 5.1 · DRF · PostgreSQL 16 · schema-per-tenant
- **Frontend** — Next.js 15 (App Router) · TypeScript · Tailwind v4 · TanStack Query
- **Monorepo** — pnpm workspaces + Turborepo, with a generated OpenAPI type contract

---

## Multitenancy in one paragraph

Each institution owns a **dedicated PostgreSQL schema** (`django-tenants`), so
**no application query filters by tenant by hand** and there is no way to forget
one. The `public` schema holds the tenant registry, platform staff and the
credential table; it has no academic or billing tables at all.

**One hostname serves the whole platform.** Nothing about a request says which
school it is for, so the school is selected by the caller's access token:
`TenantJWTAuthentication` reads the signed `tenant_schema` claim, points the
connection at that schema, and re-reads the membership before honouring it.
`PublicSchemaMiddleware` puts the connection back on `public` when the request
ends — connections are reused, and a leaked schema would serve the next caller
another school's data.

Consequences worth knowing up front:

- There is no `tenant_id` parameter anywhere in the API, and no per-school
  hostname either. Signing in decides which school you are in; `POST
  /api/v1/auth/switch/` changes it without a second sign-in.
- `email` identifies **one person platform-wide**. It has to: the login form has
  nothing else to go on. Credentials live once, as a `PlatformIdentity` in the
  public schema, and a `Membership` records which schools that person may work
  at and in what role.
- The school-local `users.User` row still exists — enrolments, invoices and
  permissions all point at it — created on first sign-in and linked by a bare
  `identity_id` UUID, with an unusable password. One credential means one thing
  to change, and nothing to keep in step.
- A signed claim is authentic but never sufficient: membership is re-read on
  every request, so revoking access takes effect on the next one rather than
  whenever the token happens to expire. A claim for a school you do not belong
  to is `403 tenant_mismatch`.

---

## Prerequisites

| Tool | Version used | Notes |
| --- | --- | --- |
| Docker + Compose | v2+ | the only hard requirement for running the stack |
| Node | 20.9+ | needed for the E2E suite and local (non-Docker) frontend work |
| pnpm | 10+ | `corepack enable` if absent |
| Python | 3.12+ | only for running the backend **outside** Docker |
| GNU gettext | optional | bundled in the API image; on the host it is only needed to *extract* translations — see [i18n](#internationalization) |

---

## Quick start (Docker)

```bash
# 1. Build and start db + api + web
docker compose up -d --build

# 2. Create a school (the public tenant is bootstrapped automatically)
docker compose exec api python manage.py create_school \
    --schema northfield --name "Northfield School" \
    --admin-email admin@northfield.test --admin-password 'School!2026dev'

# 3. Optional: fill it with demo data
docker compose exec api python manage.py seed_demo --schema northfield
```

Then open **<http://localhost:3000/es>** and sign in with
`admin@northfield.test` / `School!2026dev`.

The dev stack also creates the **platform operator** —
`admin@platform.test` / `Platform!2026dev` — who signs in at the same address and
lands on the console at `/es/platform` instead of a school dashboard. Override
either with `PLATFORM_ADMIN_EMAIL` / `PLATFORM_ADMIN_PASSWORD`.

One hostname serves every school: signing in decides which one you are in, and
the switcher in the top bar moves between them if the account has more than
one.

Those credentials are for a throwaway local stack. Anything reachable from the
internet needs a real password, and `seed_demo` generates one for the accounts it
creates — see [docs/deployment.md](docs/deployment.md).

If 3000/5432/8000 are already taken, every port is configurable:

```bash
WEB_PORT=3002 API_PORT=8001 POSTGRES_PORT=5433 docker compose up -d
```

Convenience wrappers: `pnpm up`, `pnpm down`, `pnpm logs`, `pnpm seed`,
`pnpm school -- --schema <name> --name "<Name>" …`.

### What the container does on boot

`apps/api/scripts/docker-entrypoint.sh` enforces the bootstrap order that
`django-tenants` requires — get it wrong and *every* URL returns 404:

1. wait for Postgres (`pg_isready`),
2. `migrate_schemas --shared` (public schema),
3. `bootstrap_public` — create the `Client` row for `public`, and the platform
   operator when `PLATFORM_ADMIN_EMAIL`/`PLATFORM_ADMIN_PASSWORD` are set,
4. `migrate_schemas --tenant`.

| URL | What |
| --- | --- |
| `http://localhost:3000/es` | the app (Spanish; `/en` for English) |
| `http://localhost:8000/api/docs/` | Swagger UI |
| `http://localhost:8000/admin/` | Django admin (platform operators) |
| `http://localhost:8000/api/health/` | probe; reports the resolved schema |

### Production images

`docker-compose.prod.yml` builds the `prod` targets — gunicorn + WhiteNoise for
the API, a Next.js standalone bundle for the web app — and runs them locally so
the images can be smoke-tested:

```bash
export DJANGO_SECRET_KEY=$(openssl rand -base64 32) \
       POSTGRES_PASSWORD=$(openssl rand -base64 24) \
       API_PORT=8001 WEB_PORT=3003 \
       DJANGO_ALLOWED_HOSTS=demo.localhost,localhost,127.0.0.1,.localhost,api \
       PUBLIC_DOMAIN=localhost
docker compose -f docker-compose.prod.yml up -d --build

# The school's domain is the *web* host, because that is what the browser uses.
docker exec erp_api_prod python manage.py create_school \
    --schema demo --name "Demo School" --domain demo.localhost \
    --admin-email admin@demo.test --admin-password 'Demo!2026pass'
```

Then open `http://demo.localhost:3003/es`.

This stack mirrors the deployed topology: the browser talks only to the web
origin and `/api` is proxied to gunicorn, with Django resolving the tenant from
`X-Forwarded-Host`. Three things differ from a real deployment, all because
nothing terminates TLS locally:

- `DJANGO_SECURE_SSL_REDIRECT` is off — with it on, every request would 301 to an
  https port that is not listening.
- `AUTH_COOKIE_SECURE` is off — a `Secure` cookie is set but never sent back over
  plain http, so the session would break.
- Throttle limits are the strict production ones, so the full E2E suite (which
  logs in on every test) will trip them. Run `e2e/auth.spec.ts` alone here.

The two stacks use distinct compose project names, so `down -v` on one cannot
destroy the other's data.

---

## Deploying

See **[docs/deployment.md](docs/deployment.md)** for the full runbook. The short
version: Vercel serves the app and proxies `/api` to Django on Render, so the
browser only ever talks to one origin.

That is load-bearing rather than cosmetic — the refresh cookie is host-only, so a
split deployment would lose the session on every reload — and it means a
single-school demo needs no custom domain at all. `render.yaml` provisions the
API and its database; the three variables it leaves blank depend on the Vercel
URL.

Two things that will bite if skipped: `API_PROXY_TARGET` must exist at **build**
time (Next bakes rewrites into the route manifest), and the database must be a
**direct** connection, never a transaction-mode pooler — `SET search_path` is
session state, so pooling can route a query to the wrong school's schema.

Render's free tier also sleeps after ~15 minutes, so an external pinger
(cron-job.org) hits `/api/health/` every 10 minutes; otherwise the first visit
waits ~50s for a cold start.

---

## Running without Docker

```bash
pnpm db:up                      # just PostgreSQL in a container
pnpm api:venv                   # apps/api/.venv + requirements/dev.txt
cp apps/api/.env.example apps/api/.env      # then set DJANGO_SECRET_KEY
cd apps/api
.venv/bin/python manage.py migrate_schemas --shared
.venv/bin/python manage.py bootstrap_public --email admin@platform.test --password 'change-me'
.venv/bin/python manage.py create_school --schema northfield --name "Northfield School" \
    --admin-email admin@northfield.test --admin-password 'change-me'
cd ../.. && pnpm install
cp apps/web/.env.example apps/web/.env.local
pnpm dev                        # turbo: web on :3000, api on :8000
```

---

## Layout

```text
school-admin-erp/
├── apps/
│   ├── api/                      # Django project
│   │   ├── config/settings/      # base · dev · prod
│   │   ├── apps/
│   │   │   ├── core/             # base models, soft delete, error envelope, i18n
│   │   │   ├── tenants/          # institution registry  (public schema only)
│   │   │   ├── users/            # identity             (public AND per-school)
│   │   │   ├── authentication/   # JWT issuance + tenant claim check
│   │   │   ├── academic/         # years, programmes, subjects, enrollments
│   │   │   └── billing/          # invoices, lines, payments
│   │   ├── locale/es/            # translation catalogue
│   │   ├── scripts/              # compile_messages.py (msgfmt replacement)
│   │   └── tests/                # architecture guard tests
│   └── web/                      # Next.js app
│       └── src/
│           ├── app/[locale]/     # localized routes
│           ├── messages/         # es.json · en.json
│           ├── features/         # auth · dashboard  (mirrors the Django apps)
│           ├── components/ui/    # shadcn-style primitives
│           ├── components/layout/# sidebar · topbar · switchers
│           ├── i18n/             # next-intl routing/navigation/request
│           └── lib/              # axios client, token store, query client
├── packages/api-types/           # generated TS types from OpenAPI
└── docs/design-system.md         # the visual contract
```

---

## Architectural rules, and how they are enforced

`apps/api/tests/test_architecture.py` checks these by introspection, so a
violation fails the build rather than surviving code review:

1. **No ORM relations between distant contexts.** `billing` holds no ForeignKey
   into `academic`; it stores `enrollment_id` / `student_id` / `program_id` as
   UUIDs plus a snapshot of the labels it prints, and reads live academic facts
   through `apps.academic.services` (plain dataclasses). Extracting billing means
   changing that one module.
2. **Mandatory soft delete.** `apps.core.models.BaseModel` gives UUID pk +
   timestamps + `is_active`/`deleted_at`, and overrides `delete()` **down to the
   queryset**, so `.filter(...).delete()` deactivates too. `hard_delete()` is the
   explicit escape hatch. Exemptions live in one documented dict — currently only
   `tenants.Domain`, because a "soft-deleted" hostname that still resolved would
   keep routing traffic to a decommissioned domain.
3. **Tenant isolation.** Business apps must be in `TENANT_APPS` and absent from
   `SHARED_APPS`; the registry is the reverse. Any app owning models but listed in
   neither is caught too — `migrate_schemas` would silently skip its tables.
4. **The identity boundary is a UUID.** `users.User.identity_id` points at a row
   in the *public* schema, so it must not be a ForeignKey — Postgres would accept
   one, because `public` is on every schema's search path, and moving a school to
   its own database would then be impossible. A guard asserts it stays a plain
   `UUIDField` and that no per-schema model holds a relation into `identity`.
   Another asserts `PlatformIdentityBackend` still precedes `ModelBackend`: were
   the order to flip, a stale password left in a school's own table would open
   the door.

```bash
cd apps/api && .venv/bin/pytest tests/test_architecture.py -q   # 17 passed
```

---

## Permissions

Two mechanisms that look alike and are not.

**Rank** (`apps/core/roles.py`) is an administrative ladder: platform operator →
school administrator → coordinator → accountant → teacher → guardian → student.
It answers *who may act on whom*. Nobody may act on someone at or above their
own rank, which is what stops a coordinator editing the administrator who
appointed them, and what stops anyone appointing their own equal — granting a
peer role is indistinguishable from self-promotion the moment the appointee
returns the favour. The one exception is the top role, or the platform could
never gain a second operator except by editing environment variables.

**Reach** (`apps/core/modules.py`) is per module and is *declared, not derived*.
An accountant sits below a coordinator on the ladder and is nonetheless the only
one of the two who belongs in billing. A single ordering would have to choose
between letting coordinators into invoices and locking accountants out, and both
are wrong — so each module names the roles that read it and the roles that write
it.

| Module | Reads | Writes | Optional |
| --- | --- | --- | --- |
| Users | administration | school admin | no |
| Academic | teaching | administration | yes |
| Subjects | teaching | administration | yes |
| Gradebook | teaching | teaching | yes |
| Billing | finance | finance | yes |
| Schedule | teaching | administration | yes |

The gradebook is the one module teachers **write**. Recording marks is their
job, so the module allows it and an object-level rule narrows it to the subjects
they are actually assigned — otherwise any teacher could alter any other
teacher's marks, and the record would attribute the claim to the wrong person.
Coordinators and administrators are exempt, because somebody has to be able to
correct a mark after a teacher has left.

A student therefore reaches no module at all — only their own profile, at
`/users/me/`. Reading the staff directory used to be open to every signed-in
user, which handed a student their teachers' addresses.

**Switching modules off.** An institution stores what it has *disabled*, not
what it has enabled: a module shipped in a later release is then live everywhere
by default instead of silently missing from every school provisioned before it
existed. A disabled module returns `403 module_disabled` to everyone including
the school's administrator — "off for most people" is not a setting anyone can
reason about. `users` cannot be switched off, because a school nobody can
administer is not a working school.

The interface mirrors all of this in `apps/web/src/lib/access.ts`, and only
mirrors it. Every rule is re-checked server-side; what the mirror buys is that
screens a person cannot use are not offered. Before it existed, a school
administrator could open the operator console and be shown its tables and its
"new institution" button, each of which came back 403 — the boundary held and
the screen lied.

---

## Authentication and hardening

**Who a person is.** By default an account belongs to one school and lives in
that school's schema. Someone who works at several gets a `PlatformIdentity` in
the public schema instead: one password, checked once, plus an explicit
`Membership` per school recording the role they hold there. The school-local row
still exists — enrollments, invoices and permissions all point at it — and is
created on first sign-in, linked by a bare `identity_id` UUID and left with an
unusable password, because a second copy of the credential is a second thing
able to drift.

Access can be withdrawn from either end, and both are honoured: the platform
revokes the membership, or the school deactivates the account. The school's
decision is not overridden on the next sign-in — an earlier draft reactivated
the local row every login, which would have let an administrator deactivate
someone and watch them sign back in with nothing on screen to explain it.

Two ordering details carry weight. The password is verified *before* membership
is consulted, so "you have no access to this school" is indistinguishable from
"wrong password" and the login form cannot be used to enumerate who works
where. And `PlatformIdentityBackend` runs before `ModelBackend`, so a stale
password sitting in a school's own table can never answer first.

Switching schools is a change of hostname, because the hostname is what selects
the tenant. The session does not travel with it: the refresh cookie is
host-only, which is the same property that makes cross-tenant replay impossible,
so the other school asks for the password again. The switcher in the top bar is
therefore a list of links, and it renders nothing at all for the single-school
accounts that are the norm.

**Tokens.** The access token is held in JavaScript memory only — it dies with the
tab. The refresh token is delivered as an `httpOnly; SameSite=Lax` cookie scoped
to `/api/v1/auth/`, so no script can read it and it is not attached to ordinary
API calls. A successful XSS can therefore act only while the page is open,
instead of exfiltrating a long-lived credential. Rotation plus blacklisting means
a stolen refresh token is good for one use.

**Why the app and the API share a hostname.** Browsers only attach a
`SameSite=Lax` cookie to a *same-site* request. Cookies and same-site checks
ignore the port, so `localhost:3000` → `localhost:8000` is same-site and the
cookie is sent. Pointing the frontend at an API on a different registrable
domain is **not** same-site, and gives up cookie auth entirely — which is what
`NEXT_PUBLIC_API_ORIGIN` exists for, and why it needs `AUTH_REFRESH_IN_BODY` on
the server.

That the cookie is host-only also used to make switching schools mean signing in
again, because each school had its own hostname. On one domain the session
simply moves: `POST /api/v1/auth/switch/` re-issues it against another of the
caller's schools.

**Rate limiting.** Login carries *two* limits, because the threats differ:

| Scope | Default | Guards against |
| --- | --- | --- |
| client address (`THROTTLE_LOGIN`) | `30/min` | volume from one address |
| email (`THROTTLE_LOGIN_EMAIL`) | `10/min` | brute force on one account |
| address, refresh (`THROTTLE_REFRESH`) | `60/min` | refresh abuse |

The schema used to be part of these keys, supplied by the hostname before the
request body was read. There is no such hint any more — finding out which school
someone belongs to is the whole job of login — so the address limit is shared
across institutions behind the same NAT. It is why that limit is generous and
the per-account one, which now keys on a platform-wide unique email, is not.

The per-address limit has to stay generous: a school's staff usually share one
NAT egress address, so a tight limit there locks out the whole institution rather
than an attacker. The strict limit belongs on the email, which is the dimension
brute force actually walks — and being address-independent, it still holds when
an attacker rotates addresses.

Counters live in the cache, which makes the cache backend a security decision:
the in-memory default is *per process*, so N gunicorn workers grant N times the
allowance — set `REDIS_URL` in any multi-worker deployment.

The dev stack in `docker-compose.yml` deliberately relaxes these, because the
end-to-end suite logs in on every test. A saved browser session cannot be reused
there: refresh tokens rotate and blacklist their predecessor, so a stored cookie
jar is good for exactly one restore. Production keeps the strict defaults, and
the throttles themselves are covered by the pytest suite.

**Before deploying**, confirm: `AUTH_COOKIE_SECURE=True` (forced by `prod.py`),
`DJANGO_SECURE_SSL_REDIRECT` left on behind a TLS terminator, `REDIS_URL` set,
and `DJANGO_USE_X_FORWARDED_HOST` enabled **only** if a proxy you control
rewrites the host — a client able to set that header could otherwise choose its
own tenant.

## Internationalization

Spanish is the default; English is fully supported.

**Precedence** (highest first): an explicit `Accept-Language` header → the user's
`language` profile field → `settings.LANGUAGE_CODE`. The header must win, or the
UI language switcher would be silently overridden by a stored preference and API
messages would disagree with the interface. The frontend sends the header on every
request via an Axios interceptor tied to the URL locale.

Translatable **database** fields use `django-modeltranslation` (`name_es`,
`name_en`, …) on programmes and subjects; registration codes are deliberately not
translated.

```bash
# Extract new source strings — REQUIRES GNU gettext (apt install gettext)
cd apps/api && .venv/bin/python manage.py makemessages -l es -l en

# Compile — pure Python, no gettext needed
.venv/bin/python scripts/compile_messages.py
```

`scripts/compile_messages.py` exists because `manage.py compilemessages` shells
out to `msgfmt`, which is not installed everywhere (including this project's
build environment) — that would otherwise make translated API responses
undeployable. It replaces `msgfmt` only; extraction still needs gettext.

---

## The API type contract

The frontend does not hand-write API types. Django generates OpenAPI, and
`openapi-typescript` turns it into TypeScript. There are **two** documents because
there are two surfaces on two hosts:

```bash
pnpm --filter @erp/api       run schema     # Django  -> openapi{,-public}.yaml
pnpm --filter @erp/api-types run generate   # yaml    -> src/schema{,-public}.d.ts
```

Feature code imports friendly aliases (`User`, `Invoice`, `Institution`) from
`@erp/api-types`, so an API rename becomes one type error in `src/index.ts` rather
than many across the app. Regenerate after any serializer change.

---

## Testing

```bash
pnpm test          # backend suite, then the browser suite
pnpm test:api      # pytest inside the api container
pnpm test:e2e      # Playwright against the running stack
```

### Backend — pytest (213 tests)

Runs against a **real** Postgres with real tenant schemas, because the thing most
worth testing (host → schema routing) cannot be mocked.

- `conftest.py` provisions two school schemas **once per session** — creating a
  tenant runs the whole `TENANT_APPS` migration set, so it is far too slow per
  test — and hands out API clients pinned to each school's host. Tokens come
  from the real login endpoint rather than `force_authenticate`, since the tenant
  claim is added during issuance and validating it is the point.
- Two tenants exist so isolation is *proved*, not assumed: cross-tenant reads,
  duplicate emails across schools, and replaying school A's token against school
  B's host (`403 tenant_mismatch`).
- Also covered: role permissions, soft delete (including that
  `.filter(...).delete()` cannot bypass it), `Accept-Language` on both errors and
  translated model fields, and the billing↔academic boundary — invalid
  enrollment refused, labels snapshotted at issue time, invoices surviving a
  deleted enrollment because there is no FK to cascade.

`pytest.ini_options` passes `--ds=config.settings.test` explicitly: that flag
outranks the `DJANGO_SETTINGS_MODULE` env var the image sets, and without it the
suite silently runs on dev settings where `ALLOWED_HOSTS` rejects the per-tenant
hostnames.

### Frontend — Playwright (39 tests)

```bash
# First run only:
pnpm --filter @erp/web exec playwright install chromium

# Point at the stack (defaults to :3000)
E2E_BASE_URL=http://localhost:3002 pnpm test:e2e
```

Drives a real browser against the running stack: login and refresh-token
restore, session survival across a language switch, and each module's list,
filters, create, validation and soft-delete flows. Chromium is launched with
`--host-resolver-rules=MAP *.localhost 127.0.0.1` so it can reach a school's API
host. The suite runs serially — it mutates shared school data — and fails on
unexpected console errors.

### Static checks

```bash
docker compose exec api ruff check . && docker compose exec api ruff format --check .
docker compose exec api python manage.py check
pnpm --filter @erp/web typecheck && pnpm --filter @erp/web lint && pnpm --filter @erp/web build
```

---

## Module status

| Module | State |
| --- | --- |
| Dashboard | KPIs from live API counts; trend chart on **sample data** (labelled in the UI) |
| Students | List, search, pagination, sorting, create, edit, deactivate |
| Academic | Academic years and programmes (per-language name/description editing) |
| Subjects | List, programme filter, create, edit, deactivate, teacher assignment |
| Users | Full staff directory with role assignment; `platform_admin` is not grantable from a school |
| Academic → Enrollments | Enrol a student into a programme for a year; status and enrolment date |
| Gradebook | Evaluation periods, assessments with their own scale and weight, marking a column at a time, weighted period averages |
| Billing | Invoice list with status filter, issue an invoice, detail with lines/payments, record payment |
| Platform console | Provision and edit schools (a name is all it takes — the Postgres schema is derived), set their currency, brand colour and **which modules they run**, manage the users inside any school |
| Platform → People | Cross-school identities: one credential, plus which schools each person may work at and in what role |
| Settings | Institution (read-only), profile, language, password change |
| Schedule | **Placeholder** — needs a timetable/attendance domain that does not exist yet |

## What is not built yet

- **Attendance and timetables.** The Schedule module is a placeholder, and the
  dashboard's trend chart renders sample data. `sampleWeeklyTrend()` documents
  the shape a future `GET /api/v1/academic/attendance/weekly/` should return.
  Both need a concept the domain does not have yet — a **student group** — since
  attendance is taken per session and a session is a group meeting a subject at
  an hour.
- **Competency-based evaluation.** Marks are numeric, with a scale and a weight
  per assessment. Rubrics, indicators and learning goals are not modelled, and a
  half-built version of them would be worse than their absence.
- **Report cards and transcripts.** The period average exists; turning it into
  an official document (SEP in Mexico, and the equivalents elsewhere) is the
  next step that depends on it.
- **Upcoming events / recent activity cards** — placeholder content; there is no
  academic calendar or audit log yet.
- **FullCalendar** is in the intended stack but not installed; nothing renders a
  calendar yet and an unused dependency would just rot. TanStack Table **is** now
  in use for every list screen.
- **Admin password reset.** Editing a user cannot change their password; only the
  account owner can, via Settings.
- **Dashboard metrics** are four separate `count` queries. Past a handful of
  tiles, replace them with one `GET /api/v1/dashboard/metrics/` aggregate.

## Verified on this machine

**Backend** — 213 pytest tests pass (17 architecture guards + 196
API/integration tests against real tenant schemas) · Django checks clean · no
migration drift · ruff check and format clean · the OpenAPI schema generates with
0 errors and matches the committed copy.

**Multi-currency** — a school bills in MXN or USD, set per institution. An
invoice issued with no `currency` inherits the school's; changing the setting
from the platform console changes what the next invoice is denominated in, and
an unsupported code is rejected rather than stored. Verified against the running
stack, not only in tests.

**Per-school branding** — each institution sets one hex colour; the primary,
ring and accent tokens, the dark-mode variant and the contrasting ink are all
derived from it, so no configuration produces unreadable text. It is served
unauthenticated by hostname and inlined server-side, which is what puts a
school's colour on the login page with no flash of the default palette.

**Cross-school identity** — verified against the running stack: one person, one
password, administrator at one school and teacher at another, each with its own
currency and colour. The credential lives once in the public schema; a failed
login cannot be used to discover which schools employ someone, because "no
membership here" and "wrong password" return the identical response.

**Privilege boundaries** — a school administrator cannot grant `platform_admin`,
to a colleague or to themselves: the role is only assignable in the public
schema, the roles endpoint stops offering it inside a school, and the platform
console's cross-schema requests leave the connection back on `public`.

**Isolation** — confirmed directly in PostgreSQL: `academic_*` and `billing_*`
tables exist **only** in a school schema, `tenants_client` only in `public`.
Cross-tenant token replay is rejected with `403 tenant_mismatch`.

**Frontend** — typecheck, lint and production build clean (22 static pages) ·
30 Playwright tests pass in a real browser against the Docker stack, covering
login/refresh/logout, language switching with session retention, every module's
list, filter, create, validation and soft-delete flows, and an explicit check
that no JWT is reachable from `localStorage`, `sessionStorage` or
`document.cookie` — with zero unexpected console errors.

**Docker** — dev stack (`db` + `api` + `web`) boots healthy and serves all
routes; the production stack builds and boots too, with gunicorn serving the API,
WhiteNoise serving static files, the Next standalone bundle serving both locales,
and tenant provisioning plus login working end to end.

**CI** — five GitHub Actions jobs (backend, frontend, OpenAPI contract freshness,
Playwright end-to-end against the Docker stack, production image build). Every
command was run locally first; the pipeline itself has not executed on GitHub.

---

<!-- Agrega capturas en docs/screenshots/ -->

---

## Desarrollado por Francisco Javier Laguna

[GitHub](https://github.com/jlaguna553) · [LinkedIn](https://www.linkedin.com/in/francisco-javier-laguna-mondrag%C3%B3n-80a798154/) · [CV Online](https://cv-online.jlaguna553.workers.dev/v/xrdcnyej)
