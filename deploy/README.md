# Production deployment

This directory contains the production-only deployment contract. Local development continues to use the root `docker-compose.yml`.

Harbor registry architecture, credentials, lifecycle operations, monitoring, and recovery guidance are documented in [`docs/harbor.md`](../docs/harbor.md).

## Runtime layout

- Django runs from an immutable image under Gunicorn as an unprivileged user.
- The backend publishes only `127.0.0.1:8000`; host Nginx is the sole HTTP entry point.
- Static assets are collected while building the image and served by WhiteNoise.
- PostgreSQL is not published to the host and stores data in `ladyshelf_postgres_data`.
- Migrations and role bootstrap are explicit release steps, not container startup side effects.

## Local production-mode test

1. Build the image:

   ```bash
   docker build --tag wahi-backend:local .
   ```

2. Create a temporary environment file from `backend.env.example`. Set `BACKEND_IMAGE=wahi-backend:local`, use test-only secrets, and keep `SASAPAY_BASE_URL` on the sandbox.
3. Validate and launch:

   ```bash
   docker compose --env-file /path/to/test.env -f deploy/compose.prod.yml config --quiet
   docker compose --env-file /path/to/test.env -f deploy/compose.prod.yml up -d
   curl -H 'Host: api.ladyshelf.site' -H 'X-Forwarded-Proto: https' http://127.0.0.1:8000/api/v1/health
   ```

4. Stop the test stack with `docker compose ... down`. Add `--volumes` only when deliberately discarding the test database.

## VM installation contract

Install these files after Harbor is ready:

- `compose.prod.yml` → `/opt/ladyshelf/compose.prod.yml`, mode `0644`
- completed `backend.env.example` → `/opt/ladyshelf/secrets/backend.env`, mode `0600`
- scripts → `/opt/ladyshelf/scripts/`, mode `0755`
- systemd units → `/etc/systemd/system/`, mode `0644`
- `nginx-api.conf` → `/etc/nginx/sites-available/api.ladyshelf.site`, mode `0644`; preserve a rollback copy, run `nginx -t`, and reload only after loopback backend health succeeds

Set `BACKEND_IMAGE` to an immutable Harbor tag or digest. Run `scripts/release.sh` to validate the stack, pull images, start PostgreSQL, run migrations, synchronize admin roles, start the backend, and verify health.

Create the first superuser interactively after the first successful release:

```bash
docker compose --env-file /opt/ladyshelf/secrets/backend.env -f /opt/ladyshelf/compose.prod.yml exec backend python manage.py createsuperuser
```

Enable the timers only after the stack is healthy:

```bash
systemctl daemon-reload
systemctl enable --now ladyshelf-expire-orders.timer ladyshelf-backup.timer
```

The product-image timer is intentionally separate and must remain disabled until Cloudflare and
Supabase credentials are configured and its activation receives explicit approval:

```bash
systemctl enable --now ladyshelf-product-images.timer
```

Inspect or manually process the queue without enabling the timer:

```bash
docker compose --env-file /opt/ladyshelf/secrets/backend.env -f /opt/ladyshelf/compose.prod.yml exec -T backend python manage.py process_product_image_generations --limit 1
```

New batches use prompt policy `v2-controlled-variety`. Owner-directed regeneration is available only
through the guarded API/admin dialog: Hero requeues the full dependent set, while Alternate and Detail
requeue only their own draft. Explicit regeneration deletes the affected draft objects, records the
normalized structured controls, increments the revision, and derives a new seed. Automatic worker
retries reuse the already stored prompt and seed.

## Database backup and restore

`backup-postgres.sh` creates a PostgreSQL custom-format dump in `/opt/ladyshelf/backups` and deletes local dumps older than 14 days. A local dump does not protect against VM or disk loss; copy each completed dump to separately managed off-server storage before launch.

The scripts default to the Compose project name `ladyshelf`. Set `LADYSHELF_COMPOSE_PROJECT_NAME` only for isolated test stacks.

Test restore operations on a disposable database first. A production restore is a maintenance operation: stop the backend, take a final backup, recreate the target database, pipe the chosen dump to `pg_restore`, run migrations, restart the backend, and verify `/api/v1/health` plus representative catalog/order records.

## Release safety

- Never place real secrets in this repository or bake them into an image.
- Never publish ports 8000 or 5432 publicly; the production Compose mapping is loopback-only for Django and absent for PostgreSQL.
- Back up PostgreSQL before schema changes and verify that off-server copies can be restored.
- Keep SasaPay in sandbox mode until merchant production credentials and callback verification are complete.
