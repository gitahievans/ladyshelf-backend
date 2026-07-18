# Deployment handoff

Last updated: 2026-07-18 (Africa/Nairobi)

## Resume point

**Current state:** VM bootstrap, production container preparation, and a constrained Harbor installation are complete. Harbor is ready for the first immutable backend image: authenticated publisher push, production pull, and production push denial have passed through Cloudflare. Production secrets, PostgreSQL production data, and the Django deployment do not exist yet. The public API intentionally returns `503 {"status":"deployment_pending"}`.

**Next milestone:** build, scan, and push an immutable backend image to Harbor, then prepare production configuration for the first deployment. Read `AGENTS.md` and `deploy/README.md` before acting.

## Infrastructure completed

- VM: `root@157.90.244.105`, Ubuntu 26.04 LTS, 2 vCPU, 3.7 GiB RAM, 38 GiB disk.
- SSH command: `ssh -i $HOME\.ssh\id_ed25519_hetzner root@157.90.244.105`.
- `api.ladyshelf.site` is a proxied Cloudflare A record to `157.90.244.105`.
- Cloudflare uses Full (strict), Always Use HTTPS, minimum TLS 1.2, and TLS 1.3. TLS 1.1 was verified blocked. HSTS was intentionally deferred until all production hostnames are stable.
- Cloudflare Origin CA certificate:
  - certificate: `/etc/ssl/certs/api.ladyshelf.site.pem`
  - private key: `/etc/ssl/private/api.ladyshelf.site.key` (`0600`, root-only)
  - expires: 2041-07-13
- Installed/enabled: Docker 29.1.3, Compose 2.40.3, Nginx 1.28.3, UFW, Fail2ban, unattended upgrades.
- Active 2 GiB `/swapfile`; no reboot pending at setup completion.
- SSH is root key-only: password and keyboard-interactive authentication disabled.
- UFW defaults to deny inbound; port 22 is open and port 443 is allowed only from Cloudflare's published networks.
- Nginx restores `CF-Connecting-IP`, serves TLS on 443, and currently returns the deployment placeholder. The packaged default port-80 site is disabled.
- Prepared root-owned paths: `/opt/ladyshelf`, `/opt/ladyshelf/config`, `/opt/ladyshelf/secrets` (`0700`), and `/opt/ladyshelf/backups` (`0700`).
- Verified on 2026-07-18: Docker, Nginx, Fail2ban, and UFW active; only ports 22/443 listening; no containers present.

## Harbor milestone

Operational runbook: [`docs/harbor.md`](harbor.md).

- The VM remains below Harbor's official minimum sizing (2 vCPU, 3.7 GiB RAM, 38 GiB disk). The user explicitly approved a constrained same-VM installation after the memory/storage and availability risks were explained.
- Installed Harbor v2.15.1 without Trivy from the official online installer. Its SHA-256 matched GitHub release metadata: `35bfb53ee272b59134d118ff60dceb483fbf6ff6e43060c9ebec3f72a919ed1b`.
- Harbor files are under `/opt/harbor`; persistent data is under `/opt/harbor-data`; Harbor logs rotate at 20 MiB with five retained files. Database connections and job workers were reduced for this host.
- Harbor publishes only on `127.0.0.1:8081`; host Nginx remains the sole public TLS listener on 443. Docker cannot bypass UFW through a wildcard Harbor port binding.
- `registry.ladyshelf.site` is a proxied Cloudflare A record to `157.90.244.105`. A separate Origin CA ECC certificate covers only this hostname and expires 2041-07-13.
- Public registry traffic follows Cloudflare -> host Nginx -> loopback Harbor. `/api/v2.0/ping` returns `200`; unauthenticated `/v2/` returns the expected `401` token challenge.
- Created private project `ladyshelf` with a 5 GiB storage quota.
- Created separate 365-day robot accounts: publisher (repository pull/push) and production (repository pull only). Root-only credentials are stored under `/opt/harbor/credentials` (`0700`; files `0600`) and are not in Git or chat.
- End-to-end Cloudflare test passed: publisher push, production pull, and production push denial. Smoke image digest: `sha256:ac55161c57a8351807adf8f8def264bdd52667c371d0436beefebdac4341c9e2`.
- After installation, Harbor used about 143 MiB across its idle containers. Root disk use increased from 7.0 GiB to 9.1 GiB, leaving about 27 GiB. This is only idle evidence and does not remove the below-minimum operational risk.
- Shipping decision on 2026-07-18: Harbor push/pull capability is sufficient for the first backend release. The proposed keep-five-releases retention policy, weekly one-worker garbage collection, initial GC dry run, restart-survival test, and off-VM Harbor backup/restore work were deferred so the application deployment can proceed. No retention or GC schedule was applied.
- Latest read-only maintenance inspection found no existing Harbor retention policy or garbage-collection schedule. Baseline at that inspection: about 863 MiB host memory used, 2.9 GiB available, negligible swap use, root disk 26% used with about 27 GiB free, and `/opt/harbor-data` about 127 MiB.

## Repository work completed

- Production image uses pinned Gunicorn and WhiteNoise, collects compressed static assets at build time, runs as UID/GID `10001`, has a read-only-compatible filesystem, and includes a health check.
- Django is proxy-aware and production defaults enable HTTPS redirect, secure session/CSRF cookies, structured logs, and reusable DB connections while local `DJANGO_DEBUG=true` behavior is preserved.
- `deploy/compose.prod.yml`:
  - pulls `${BACKEND_IMAGE}` rather than building source;
  - binds backend only to `127.0.0.1:8000`;
  - runs PostgreSQL 16.14 with an internal-only port and named volume;
  - adds health checks, restart policies, resource limits, and log rotation.
- Operational artifacts exist for controlled releases, PostgreSQL backups, five-minute unpaid-order expiry, and daily backup timers.
- `deploy/backend.env.example` is the production secret/config template. No production values have been generated.
- PostgreSQL testing exposed and fixed a nullable-join `SELECT FOR UPDATE` issue in `admin_portal/views.py`.
- Payment notification tests no longer depend on the developer's ambient `.env` staff-recipient setting.

## Validation evidence

- Linux production image built successfully on the VM, then the test image was removed.
- Image ran as non-root UID/GID `10001`.
- Static collection: 157 files copied and 751 post-processed.
- Django deployment check completed with no errors. Remaining warnings are pre-existing drf-spectacular schema warnings plus application HSTS being delegated to Cloudflare.
- Migrations and `bootstrap_admin_roles` succeeded on PostgreSQL 16.14.
- Full PostgreSQL-backed suite: **66 tests passed**.
- Gunicorn health endpoint and WhiteNoise admin CSS returned `200`; container became healthy; root filesystem write was rejected.
- Order-expiry command executed successfully.
- Backup script produced a root-only custom-format dump; `pg_restore --list` read 224 archive entries.
- Disposable test containers, network, PostgreSQL volume, backend image, source archive, environment file, and `/tmp` directory were deleted. Nothing was deployed.

## Worktree ownership boundary

At deployment work start, these user changes already existed and must not be discarded or attributed to deployment work:

- `admin_portal/serializers.py`, `admin_portal/tests.py`
- `catalog/admin.py`, `catalog/models.py`, `catalog/serializers.py`, `catalog/tests.py`
- `checkout/services.py`, `checkout/tests.py`
- `catalog/migrations/0002_productvariant_image_url.py` (untracked)

Deployment work added or changed:

- `.dockerignore`, `.gitignore`, `.env.example`, `Dockerfile`, `requirements.txt`, `README.md`
- `config/settings.py`, `config/gunicorn.py`
- `admin_portal/views.py`, `payments/tests.py`
- `docs/environment.md`, `docs/deployment-handoff.md`, `AGENTS.md`
- everything under `deploy/`

Nothing has been staged or committed. Inspect current `git status` before continuing.

## Pending plan

### 1. Publish the backend image

- Review/commit the intended repository changes without absorbing unrelated dirty files accidentally.
- Build the image from the intended commit, tag with commit SHA (not `latest`), scan it, push to Harbor, and record the immutable digest.
- Set production `BACKEND_IMAGE` to that tag or digest.
- Monitor Cloudflare's request-size and proxy-timeout behavior while pushing the real backend image. Keep image layers within the applicable Cloudflare limit.

### 2. Prepare production configuration

- Generate strong Django and PostgreSQL secrets directly into `/opt/ladyshelf/secrets/backend.env` (`0600`). No production DB password exists yet.
- Fill real Supabase, SMTP, frontend CORS/CSRF, staff email, and SasaPay sandbox values. Keep SasaPay sandbox until live approval.
- Copy Compose/scripts/systemd artifacts to the paths specified in `deploy/README.md` with documented permissions.
- Configure an off-server destination for completed database dumps before launch.

### 3. First deployment

- Run the controlled release script: validate configuration, pull images, start DB, migrate, bootstrap roles, start backend, and verify loopback health.
- Replace the Nginx placeholder with a proxy to `127.0.0.1:8000`; pass `Host`, `X-Forwarded-For`, and `X-Forwarded-Proto`; validate and reload Nginx.
- Create the first Django superuser interactively.
- Enable expiry and backup timers only after the stack is healthy; verify a backup and test restore on a disposable database.
- Verify public health, admin/static assets, API schema, CORS/auth, checkout, SasaPay callback reachability/idempotency, email, container health, logs, restart recovery, and direct-origin blocking.
- Enable HSTS only after every intended `ladyshelf.site` hostname is permanently HTTPS-capable; start conservatively without preload/includeSubDomains.

### 4. Deferred Harbor operations

- Configure the approved retention policy to keep the five most recently pushed tags per repository.
- Configure weekly garbage collection with one worker, run an initial dry run, review the output, and verify disk usage after the first real collection.
- Verify Harbor restart survival, then recheck container health, authentication, push/pull authorization, memory, swap, disk, logs, and the loopback-only listener.
- Design and test an encrypted off-VM Harbor backup/restore process. The user chose not to perform this before the first application release; until it exists, VM or root-disk loss can destroy Harbor images, metadata, and locally stored credentials.
- The 5 GiB project quota limits growth but does not itself delete tags or reclaim blob storage. Monitor capacity manually until retention and GC are active.

## Production invariants

- No public port 8000 or 5432.
- No Django `runserver` in production.
- No automatic migrations hidden in container startup.
- No plaintext secrets in Git, images, command output, or chat.
- Use immutable image tags/digests and preserve a rollback image.
- Keep at least one verified off-server database backup before risky changes.
