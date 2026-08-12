# Deployment

A demo/portfolio deployment: **one school, Vercel for the app, Render for the API
and database.** Roughly $0/month on free tiers, with the caveats at the bottom.

Verified locally against the production images before writing this — see
[What was verified](#what-was-verified).

---

## The topology, and why it is this shape

```
browser ──► https://<app>.vercel.app          (Next.js)
                    │
                    ├── /es, /en, …           rendered by Next
                    └── /api/*  ──rewrite──►  https://<api>.onrender.com  (Django)
                                              X-Forwarded-Host: <app>.vercel.app
```

**The browser only ever talks to the Vercel origin.** That is not a style choice,
it is what makes authentication work:

- The refresh token is an `httpOnly` cookie with **no `Domain`**, so it is only
  returned to the exact host that set it. Proxying means Django's `Set-Cookie`
  reaches the browser as coming from the Vercel origin.
- Split it — app on `x.vercel.app`, API called directly at `y.onrender.com` —
  and the cookie is never sent back. Login appears to work and the session dies
  on the next reload.

**The tenant still comes from the hostname.** Next forwards the original host as
`X-Forwarded-Host`; Django trusts it because `DJANGO_USE_X_FORWARDED_HOST=True`,
and resolves the school from it. So the demo school's `Domain` row must be the
**Vercel hostname**, not the Render one.

For a single demo school this needs no custom domain at all. Multiple schools
would need one hostname each — a wildcard domain plus wildcard TLS, which is
where the free tiers stop being enough.

---

## 1. Deploy the API (Render)

`render.yaml` is a Blueprint: **New → Blueprint → point at this repo**. It
provisions the web service and a Postgres 16 instance, and generates
`DJANGO_SECRET_KEY`.

Three variables are marked `sync: false` because they depend on the Vercel URL,
which does not exist yet. Leave them for step 3.

> **Use the direct database URL, never a transaction-mode pooler.**
> `django-tenants` selects the school with a session-level `SET search_path`.
> Under transaction pooling, consecutive statements can land on different
> backends and run against the **wrong schema** — a cross-tenant data leak, not a
> performance quirk. This rules out Supabase's `:6543` pooler and Neon's pooled
> endpoint unless configured for session mode.

## 2. Deploy the app (Vercel)

Import the repo and set **Root Directory** to `apps/web`. Leave the build and
install commands on their defaults — Vercel detects pnpm workspaces and
Turborepo on its own, installs from the workspace root and builds the Next app.

There is deliberately **no `vercel.json`**. An earlier one failed the deploy two
seconds in: it pinned `regions` (a Pro-plan feature, rejected outright on Hobby),
stubbed out `installCommand`, and drove pnpm by hand with `cd ../..`, fighting
the Turborepo detection Vercel reports in its own log. The defaults work.

Set one environment variable:

| Variable | Value | Why |
| --- | --- | --- |
| `API_PROXY_TARGET` | `https://<api>.onrender.com` | where `/api/*` is forwarded |
| `NEXT_PUBLIC_API_PORT` | *(leave unset)* | unset ⇒ same-origin, which is the proxy |

`API_PROXY_TARGET` must be available **at build time**: Next evaluates
`rewrites()` during the build and bakes the result into the route manifest.
Setting it only at runtime yields an image with no proxy and a 404 on every API
call.

## 3. Point the API back at the app

Variables marked `sync: false` in `render.yaml` are **not created** by the
Blueprint — Render omits them entirely rather than adding them blank. Add each
by hand under **Environment → Add Environment Variable**:

```bash
DJANGO_ALLOWED_HOSTS=<app>.vercel.app,<api>.onrender.com
CSRF_TRUSTED_ORIGINS=https://<app>.vercel.app
PUBLIC_DOMAIN=<api>.onrender.com
```

Two details, each worth a failed deploy:

- `DJANGO_ALLOWED_HOSTS` takes **hostnames**, comma separated, no scheme.
  `CSRF_TRUSTED_ORIGINS` takes **origins**, with `https://`.
- **`PUBLIC_DOMAIN` is the API's own hostname, not the frontend's.** Render's
  health check requests `<api>.onrender.com/api/health/`; a host with no `Domain`
  row resolves to no tenant and returns 404, so the deploy waits forever on a
  health check that can never pass. The frontend's hostname belongs to the
  *school*, created in the next step.

### Create the platform operator

Free plans have no shell, so `createsuperuser` can never be run. Add these and
the account is created on the next boot (existing emails are skipped, so it is
safe on every redeploy):

```bash
PLATFORM_ADMIN_EMAIL=you@example.com
PLATFORM_ADMIN_PASSWORD=<something-strong>
```

This account is **not** a school administrator. It signs in on the API's own
host -- `PUBLIC_DOMAIN` -- and is the only one that can reach the operator
console, the Django admin, and the cross-school identity endpoints.

Check it worked:

```bash
curl -s -X POST https://<api>.onrender.com/api/v1/auth/login/ \
  -H 'Content-Type: application/json' \
  -d '{"email":"you@example.com","password":"..."}'
```

### Reaching the platform console

Nothing special is needed. One hostname serves the whole platform, so the
console lives at `https://<app>.vercel.app/es/platform` alongside every other
screen, and `IsPlatformAdmin` is what separates it — not the URL.

Sign in there with the operator account created above. School staff signing in
at the same address land in their own school and never see it.

## 4. Create the school

Free plans have **no shell**, so the school is provisioned from configuration
rather than a one-off command. Add these and redeploy:

```bash
DEMO_SCHOOL_SCHEMA=demo                 # unset disables provisioning entirely
DEMO_SCHOOL_NAME=Demo School
DEMO_CURRENCY=MXN                       # or USD — what the school bills in
DEMO_BRAND_COLOR=#1d4ed8                # six-digit hex; the palette derives from it
DEMO_ADMIN_EMAIL=admin@demo.test
DEMO_ADMIN_PASSWORD=<something-strong>  # omit to have one generated
DEMO_SEED=true
```

There is no hostname here any more. A school is not reached at an address of its
own: it is selected by whoever signs in, so provisioning creates the schema, the
administrator and (optionally) sample data, and nothing else.

On boot the entrypoint runs `provision_demo`, which is idempotent by design: it
creates the tenant and administrator if missing, seeds sample data once, and is
a no-op on every later deploy. `DEMO_CURRENCY` and `DEMO_BRAND_COLOR` are only
applied when set, so a redeploy will not overwrite what an operator configured
in the console.

Omit `DEMO_ADMIN_PASSWORD` and one is generated and printed **once** in the
deploy log — the only channel available without a shell. Copy it before the log
scrolls away.

`DEMO_SEED=true` creates 48 students and 7 teachers as **real, working logins**,
sharing one generated password that is printed once. They are only reachable by
someone who reads that log — unlike a hard-coded password in a public repository,
which would let anyone read the roster of your deployed demo.

With a shell available, the equivalent one-off is:

```bash
python manage.py create_school --schema demo --name "Demo School" \
  --admin-email admin@demo.test --admin-password '...'
python manage.py seed_demo --schema demo
```

The console asks for less than this: a name, and the schema is derived from it.
`--schema` survives on the command line because an operator running one-off
commands often wants to name it themselves.

### Upgrading a deployment that predates the single domain

The entrypoint runs `migrate_users_to_identities` on every boot, so this happens
by itself. It is worth knowing what it does, because it is the step that decides
whether anyone can sign in afterwards.

Credentials used to live inside each school's schema, findable because the
hostname said which schema to look in. There is no such hint now, so every
account is consolidated into one `PlatformIdentity` in the public schema, with a
`Membership` per school. Password hashes are **copied, not reset** — nobody has
to change a password for this.

One case it will not decide for you. If two schools hold the same email address
with different passwords, that is either one person who set two, or two
different people — indistinguishable from the database. Merging would hand one
person's account to the other, so the command migrates the first and reports the
rest by name and school:

```
1 account(s) could not be migrated because the same email belongs to a
different person at another school.
  - ana@example.com at Riverside Academy (riverside)
```

Those accounts cannot sign in until someone changes one of the addresses. The
boot does not fail over it: refusing to start would take the platform down for
everyone else.

## 5. Stop the API falling asleep

Point an external pinger at `/api/health/` every 10 minutes — see
[Keeping the demo awake](#keeping-the-demo-awake). Skip this and the first visit
after a quiet spell takes ~50s, which looks like a broken link.

---

## Configuration reference

| Variable | Where | Notes |
| --- | --- | --- |
| `DJANGO_SECRET_KEY` | API | no default; the app refuses to boot without it |
| `DJANGO_ALLOWED_HOSTS` | API | must include the Vercel host |
| `CSRF_TRUSTED_ORIGINS` | API | required for the Django admin behind the proxy |
| `DJANGO_USE_X_FORWARDED_HOST` | API | `True`. Only safe because Vercel is the sole ingress |
| `AUTH_COOKIE_SECURE` | API | defaults to `True` in prod; never disable outside a local http smoke test |
| `RUN_MIGRATIONS_ON_START` | API | `true` is fine for one instance; see below |
| `GUNICORN_WORKERS` | API | `1` on the free plan; raise only with `REDIS_URL` set |
| `REDIS_URL` | API | throttle counters. Unset ⇒ per-process counters ⇒ N workers grant N× the allowance |
| `API_PROXY_TARGET` | Vercel | build-time |
| `NEXT_PUBLIC_API_PORT` | Vercel | leave unset |

### Migrations

The container runs `migrate_schemas` on boot, which is convenient for one
instance and **wrong for more than one** — replicas racing on the same DDL. Once
you scale past one:

```bash
RUN_MIGRATIONS_ON_START=false          # on the service
bash /app/scripts/docker-entrypoint.sh migrate   # as a pre-deploy/release step
```

---

## What was verified

The production images were built and run locally in exactly this topology
(browser → Next → `/api` rewrite → gunicorn), with a school whose domain was the
*web* host:

- tenant resolved from `X-Forwarded-Host` (`{"schema": "demo"}`)
- login set an `httpOnly; SameSite=Lax` cookie on the web origin, with no refresh
  token in the response body
- refresh worked from the cookie alone, and the rotation chain held across
  repeated refreshes
- an authenticated request through the proxy returned the right user
- WhiteNoise served the admin's static files
- the 8-test authentication E2E suite passed against the production images

Two bugs were found doing this, both now fixed: the rewrite dropped DRF's
trailing slash (turning every proxied call into a 301 that a POST cannot
follow), and the client built an absolute API URL that discarded the browser's
port, addressing `:80` instead of the real one.

## Keeping the demo awake

Render's free tier sleeps a service after ~15 minutes of inactivity, and the next
request waits ~50s for the container to boot. On a portfolio link that someone
clicks once, that reads as broken.

This project uses an **external pinger** rather than a GitHub Actions schedule.
A scheduled workflow bills a full minute per run even when it does nothing, so a
10-minute cadence is ~4,300 minutes/month against the 2,000-minute free
allowance on a private repository. An external pinger costs nothing either way.

### Setting it up on cron-job.org

<https://cron-job.org> — free, no card required. (Not to be confused with
cronjob.com, which is a different service.)

1. Create an account and verify the email address.
2. **Create cronjob** with:

   | Field | Value |
   | --- | --- |
   | Title | `Keep ERP demo awake` |
   | URL | `https://<api>.onrender.com/api/health/` |
   | Schedule | Every 10 minutes |
   | Request method | `GET` |

   Note the **trailing slash** on `/api/health/`. Without it Django's
   `APPEND_SLASH` answers with a 301, which still wakes the service but shows up
   as a redirect rather than a clean 200 in the pinger's history.

3. Optionally enable failure notifications, so a genuinely dead API emails you.

Ten minutes leaves headroom under Render's ~15-minute idle timeout. Pinging the
health endpoint is deliberate: it is unauthenticated, does no real work, and
reports the resolved tenant schema, so its response also confirms the tenant
routing is intact rather than merely that the process is up.

### What "failed" pings mean

Free pinger plans usually cap the request timeout well below a Render cold start.
Right after a deploy, or after the schedule has been paused, the first ping may
be recorded as a timeout **even though it worked** — the request still reached
Render and started the container, and the next ping a few minutes later will
return 200. Sustained failures are the signal worth acting on, not isolated ones.

### If you would rather not

Keeping a free instance permanently awake works against what that tier is
designed for. The alternatives are Render's paid tier (~$7/month), which removes
the problem entirely, or simply accepting the cold start and telling visitors the
first load takes a moment.

## Caveats for anything beyond a demo

- **Vercel's Hobby tier is non-commercial.** A paying client needs Pro.
- **Free tiers sleep and expire.** Render's free web service idles out, and free
  Postgres instances have historically been time-limited. Verify current terms.
- **No backups are configured.** Fine for throwaway demo data, not for student
  records.
- **Real student data is a different project.** Minors' personal data brings
  GDPR obligations — data residency, retention, a processing agreement — and
  most free tiers are US-hosted.
