# Agent guidance

## Read first

- Deployment state and next actions: `docs/deployment-handoff.md`.
- Production operations: `deploy/README.md`.
- Environment contract: `deploy/backend.env.example` and `docs/environment.md`.
- Update `docs/deployment-handoff.md` after every deployment milestone; record evidence, remaining work, and any decisions.

## Mandatory user-approval gate

- Before taking a consequential action, stop, explain the proposed action, its reason, impact, risks, and alternatives, and obtain the user's explicit approval.
- Approval is required before:
  - making a major technical, architectural, security, infrastructure, deployment, or configuration decision;
  - changing code, repository files, the VM, Cloudflare, DNS, Nginx, Docker, Harbor, databases, services, firewall rules, credentials, or external systems;
  - using a tool or command that writes data, changes state, installs software, deploys, restarts services, publishes artifacts, accesses an external system, or may incur cost;
  - switching from the documented plan or using a materially different implementation approach;
  - expanding scope, choosing between meaningful alternatives, or performing a destructive or difficult-to-reverse operation.
- State exactly what approval covers. Do not treat approval for one action or phase as blanket approval for later actions.
- If new information requires a material plan change, pause and obtain fresh approval before continuing.
- Routine conversation and read-only inspection of repository files, documentation, status, logs, and system state are allowed without approval, provided they do not expose secrets or alter state.
- When uncertain whether an action is consequential, ask first.

## Repository

- Django 6 / DRF commerce backend; settings live in `config/settings.py`.
- Local development uses root `docker-compose.yml`, source mounts, Django `runserver`, and `.env`.
- Production uses `Dockerfile`, `config/gunicorn.py`, and `deploy/compose.prod.yml`.
- Never treat the root development Compose file as production configuration.

## Commands

```powershell
# Local development
docker compose up --build
docker compose run --rm backend python manage.py test
```

```bash
# Production model validation
docker compose --env-file /path/to/backend.env -f deploy/compose.prod.yml config --quiet
```

## Invariants

- Never commit `.env`, production credentials, registry credentials, database dumps, or private keys.
- Production Django must run under Gunicorn as the image's non-root user; never use `runserver`.
- Publish Django only on host loopback (`127.0.0.1:8000`); never publish PostgreSQL.
- Public API traffic must remain Cloudflare -> host Nginx -> loopback Gunicorn.
- Run migrations and `bootstrap_admin_roles` explicitly through the release workflow.
- Back up PostgreSQL before schema changes; local-only backups are insufficient for launch.
- Add model changes with migrations and test against PostgreSQL, not SQLite alone.

## Editing safety

- The worktree may contain user changes unrelated to deployment. Inspect `git status` and targeted diffs first; never reset, discard, stage, or commit unrelated changes.
- Do not edit generated `staticfiles/`, database files, or secrets.
- Preserve local development behavior when changing production settings.
- For deployment work, verify image build, `manage.py check --deploy`, migrations, full tests, health, static delivery, and backup readability.
