# Deployment handoff

Last updated: 2026-07-22 (Africa/Nairobi)

## Resume point

**Current state:** LadyShelf is deployed. PostgreSQL 16.14 and the AI product-image backend are healthy; Django is bound only to `127.0.0.1:8000`, PostgreSQL has no host port, and Nginx proxies `https://api.ladyshelf.site` through Cloudflare. The deployed source revision is `a7851a124b94642ba79a74df07bb7d9599890b57`, using `registry.ladyshelf.site/ladyshelf/backend@sha256:59e54363e4a63e0c1e0046871507b9be6936ce81ec82e5640f44b5436ed91021`. The first superuser exists. The five-minute unpaid-prepay order-expiry timer and the two-minute AI product-image timer are enabled and active.

**Next milestone:** complete owner-facing browser verification of the deployed `/admin/catalog` AI workflow and the production frontend deployment if not already verified through Vercel. Keep Namecheap as registrar and Cloudflare as authoritative DNS; do not replace Cloudflare's nameservers with Vercel's. Preserve the proxied `api` and `registry` records. Fix Supabase token verification in a separate workstream, and continue the remaining post-deployment and deferred Harbor operations below. Read `AGENTS.md` and `deploy/README.md` before acting in this repository.

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
- Nginx restores `CF-Connecting-IP`, serves TLS on 443, and proxies the API to loopback Gunicorn. The packaged default port-80 site is disabled.
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
- `deploy/backend.env.example` is the non-secret production configuration template. Production values exist only in the root-only VM environment file and are not stored in Git.
- PostgreSQL testing exposed and fixed a nullable-join `SELECT FOR UPDATE` issue in `admin_portal/views.py`.
- Payment notification tests no longer depend on the developer's ambient `.env` staff-recipient setting.

## Backend image publication milestone

- All intended application and deployment changes were committed and pushed to `main` in `e41008f9ce258f0d409d68ca9f8d5a1b23280d42` (`Prepare production deployment and Harbor registry`).
- The first scan found a fixable high-severity JWT authentication-bypass issue in PyJWT 2.12.1. That image was not published. PyJWT was upgraded to 2.13.0 and committed/pushed in `1f3f52ba5a05bc3f59e421fa86d05da0a1eb1881` (`Upgrade PyJWT for authentication security`).
- The corrected Linux image was built from a Git archive of commit `1f3f52ba5a05bc3f59e421fa86d05da0a1eb1881`. Its OCI revision label matches that full commit SHA, and its build collected 157 static files with 751 post-processing operations.
- The corrected image was scanned with checksum-verified Trivy v0.69.3, run unprivileged against a saved image archive without Harbor credentials or Docker-socket access. The scan database was downloaded on 2026-07-18.
- Corrected scan result: 3 critical, 19 high, 57 medium, 67 low, and 31 unknown findings. There were no vendor fixes available for any critical/high finding. The critical findings were Debian `perl-base` issues; one applies to 32-bit builds while this image is amd64. These unfixed base-image findings remain a tracked release risk and must be rescanned when Debian or the Python base image publishes fixes.
- The user explicitly directed that the PostgreSQL-backed test suite and production checks not be rerun for this publication. The scan and image build passed, but this release must not be represented as having current-commit test/check evidence.
- Publisher push through Cloudflare succeeded. Production pull through Cloudflare succeeded using the pull-only robot and the fully qualified digest.
- Published tag: `registry.ladyshelf.site/ladyshelf/backend:1f3f52ba5a05bc3f59e421fa86d05da0a1eb1881`.
- Initial immutable reference: `registry.ladyshelf.site/ladyshelf/backend@sha256:86740e767f16efd21f25b48f5e8f824eb48121b46da3d4bd99e5e904b9df99b4`. This was superseded before public cutover by the Gunicorn control-socket correction below.
- After transient scan/build cleanup, all nine Harbor containers were healthy, Harbor still listened only on `127.0.0.1:8081`, root disk use was 28% with about 26 GiB free, `/tmp` was 1% used, available memory was about 2.8 GiB, and `/opt/harbor-data` was about 197 MiB.

## Production configuration milestone

- Installed `/opt/ladyshelf/compose.prod.yml` (`0644`, root-owned), release and PostgreSQL backup scripts (`0755`, root-owned), and the four systemd unit/timer files (`0644`, root-owned).
- Generated independent strong Django and PostgreSQL secrets directly for production. The completed environment is `/opt/ladyshelf/secrets/backend.env`, mode `0600`, root-owned, beneath a `0700` directory. The temporary credential input was deleted locally and from the VM.
- Configured the immutable backend digest, Supabase project/JWKS URL, both production frontend origins, Gmail SMTP with TLS, the administrative/order notification recipient, SasaPay sandbox credentials and callback, production security settings, and internal PostgreSQL settings. No secret values are recorded in this repository or handoff.
- The Gmail application password and SasaPay secret had been pasted into chat. The user declined rotation and explicitly approved using them. Treat this as an accepted credential-exposure risk; rotation remains strongly recommended.
- The user explicitly declined an off-VM PostgreSQL backup destination. Local backup tooling is installed but the backup timer remains disabled. Until off-VM copies and restore tests exist, VM or root-disk loss can destroy all production database data.
- Compose configuration validation passed and resolved to the expected immutable backend digest plus `postgres:16.14-bookworm`. Required environment entries are present, and root's Docker configuration contains registry authentication for production pulls.
- No application containers were started. Ports 8000 and 5432 are not listening, both LadyShelf timers are disabled, Nginx was not changed, and the public health endpoint still returns the intentional `503 {"status":"deployment_pending"}` placeholder.

## First deployment milestone

- The initial release created a new `ladyshelf_postgres_data` volume, started PostgreSQL 16.14, applied all Django migrations through `wishlist.0001_initial`, and ran `bootstrap_admin_roles`. The Owner group synchronized 48 permissions and Attendant synchronized 14.
- The initial backend became healthy and served health/static responses, but Gunicorn 26 logged a control-server error because its default `/app/.gunicorn/gunicorn.ctl` path conflicted with the intentionally read-only container filesystem. Public Nginx remained on the placeholder while this was corrected.
- Added `control_socket_disable = True`, committed/pushed as `5273eecab837c561de800ed3fb2f04ba2bb5a74d`, rebuilt, and rescanned the exact commit. The scan matched the accepted baseline: 3 critical, 19 high, 57 medium, 67 low, and 31 unknown; no critical/high finding had a vendor fix.
- Published and production-pull verified `registry.ladyshelf.site/ladyshelf/backend@sha256:57bc9291f151d6212cda66e97ad6bb0da39fccbb54a46c25c04ecc5cc6c8ed35`.
- Atomically updated only `BACKEND_IMAGE` and recreated only the backend container. PostgreSQL's container ID remained unchanged. The corrected backend became healthy, its OCI revision label matched `5273eecab837c561de800ed3fb2f04ba2bb5a74d`, effective `control_socket_disable` was `True`, and corrected-start logs contained no error or traceback.
- Replaced the Nginx placeholder with the reviewed loopback proxy after `nginx -t` passed. Rollback copy: `/etc/nginx/sites-available/api.ladyshelf.site.placeholder-20260718T0140Z`.
- Public Cloudflare validation passed: health, admin CSS, OpenAPI schema, Swagger UI, and admin login returned HTTP 200; `https://ladyshelf.site` received the expected CORS allow-origin response. Cloudflare served HTTP/2 and returned a `cf-ray` header.
- Final isolation and capacity evidence: only `127.0.0.1:8000` was published for Django; PostgreSQL had no host listener; Nginx was active; both application containers were healthy; backend used about 182 MiB, PostgreSQL about 43 MiB, available host memory was about 2.7 GiB, negligible swap was used, and root disk was 28% used after cleanup.
- The database-backup timer remains disabled because the user declined both local-only and off-VM PostgreSQL backups. HSTS, live SasaPay, off-VM backups, restart-survival testing, and a successful real Supabase login remain pending.

## Post-deployment operations milestone

- Created the first Django superuser with username `admin` and administrative email `evanygk@gmail.com`. A database audit verified that it is active, staff, and superuser. The password is not recorded in Git or this handoff, and the one-time local and VM input files were deleted.
- Enabled and started `ladyshelf-expire-orders.timer`. It is enabled and active on a five-minute schedule; an immediate service run exited successfully and reported `Expired 0 unpaid prepaid order(s).`
- Supabase's configured JWKS endpoint was reachable over HTTPS and returned HTTP 200, but its public response was `{"keys":[]}`. Invalid bearer-token rejection works and returned HTTP 403. Successful Supabase authentication cannot be validated and is expected to fail until the project exposes an asymmetric signing key; a valid test access token is also still required for the successful-login check.
- Django's configured Gmail SMTP service accepted direct and checkout-related test messages. The user subsequently confirmed that the messages arrived in the administrative inbox, completing the email-delivery validation.
- A uniquely tagged production smoke flow passed through the public Cloudflare endpoint: delivery quote, guest prepaid order creation, and one real SasaPay sandbox checkout session all succeeded.
- The same synthetic SasaPay sandbox failure callback was submitted twice through the public callback endpoint. Both requests succeeded and produced one stable failed payment state, verifying callback idempotency for this failure case. This did not switch SasaPay to live mode.
- All temporary smoke data was removed. The flow deleted one temporary order plus its transaction and the temporary catalog records; a separate database audit found zero matching smoke products and zero matching smoke orders.
- Final infrastructure audit found the backend and PostgreSQL containers healthy, Django published only on `127.0.0.1:8000`, PostgreSQL with only its internal container port and no host listener, and the order-expiry timer enabled/active.
- Fixed Django admin login CSRF failures caused by the API Nginx site sending `Referrer-Policy: no-referrer`. Browser POSTs consequently arrived at Django with `Origin: null` and were correctly rejected. Changed only the API site's policy to `same-origin`; `nginx -t` passed and Nginx reloaded successfully without restarting the application or database. A controlled public Cloudflare round trip fetched a fresh CSRF token and submitted dummy credentials: GET and POST both returned HTTP 200, and Django reached normal credential validation rather than CSRF rejection. Rollback copy: `/etc/nginx/sites-available/api.ladyshelf.site.pre-referrer-policy-20260718T080301Z`.

## AI product-image review workflow follow-up

- Follow-up backend fixes were committed and pushed on `feature/ai-product-images` as `a7851a124b94642ba79a74df07bb7d9599890b57` (`Fix AI image review cancellation workflow`).
- The follow-up fixes initialize default Supabase storage for candidate rejection, make reject cleanup best-effort with cleanup-needed state, add owner-only `POST /api/v1/admin/image-generations/{generation_id}/cancel`, cancel queued/ready/needs-regeneration/approved/failed generation work without changing live product galleries, delete only draft `ai-drafts/` objects best-effort, recompute batch status, and add sanitized Cloudflare 400/422 diagnostics plus softened Detail prompts.
- Local verification before deployment: `docker compose run --rm backend python manage.py test admin_portal.test_image_generation` passed with 40 tests; `docker compose run --rm backend python manage.py makemigrations --check` reported no changes; `docker compose run --rm backend python manage.py check` reported no issues.
- A production image was built on the VM from a Git archive of exact commit `a7851a124b94642ba79a74df07bb7d9599890b57`, collected 157 static files with 751 post-processing operations, and was pushed to Harbor as `registry.ladyshelf.site/ladyshelf/backend:a7851a124b94642ba79a74df07bb7d9599890b57`.
- Published and deployed immutable digest: `registry.ladyshelf.site/ladyshelf/backend@sha256:59e54363e4a63e0c1e0046871507b9be6936ce81ec82e5640f44b5436ed91021`. OCI revision label matches `a7851a124b94642ba79a74df07bb7d9599890b57`.
- Environment rollback copy before the follow-up deployment: `/opt/ladyshelf/secrets/backend.env.pre-ai-review-fix-20260722T203221Z`.
- `/opt/ladyshelf/scripts/release.sh` completed successfully. No migrations were pending; `bootstrap_admin_roles` synced Owner with 48 permissions and Attendant with 14. Backend was recreated only; PostgreSQL remained healthy.
- Post-deployment verification found `ladyshelf-backend-1` running healthy on loopback `127.0.0.1:8000`, public `https://api.ladyshelf.site/api/v1/health` returned `{"status":"ok","service":"wahi-fashion-backend","version":"0.1.0"}`, and both `ladyshelf-product-images.timer` and `ladyshelf-expire-orders.timer` remained active.
- No production database backup was created for this follow-up because there were no model or migration changes. No production AI generation, Supabase storage cleanup, product gallery changes, DNS, Nginx, firewall, or frontend deployment changes were made as part of this follow-up.

## Frontend handoff decision

- Backend work was intentionally paused after the production admin login and email-delivery validations passed. The next workstream is connecting the Vercel-hosted frontend to `ladyshelf.site`.
- Namecheap remains the registrar, and its delegation must continue using the existing Cloudflare nameservers. Cloudflare remains the authoritative DNS provider; do not replace its nameservers with Vercel's.
- In the next workstream, inspect the Vercel project first and use the exact apex, `www`, and verification record values it supplies. Do not guess or hard-code general-purpose Vercel targets when project-specific targets are available.
- Configure the frontend apex and `www` records in Cloudflare as DNS-only/grey-cloud so traffic reaches Vercel directly. Choose and verify one canonical hostname plus the intended redirect in Vercel.
- Preserve `api.ladyshelf.site` and `registry.ladyshelf.site` as Cloudflare-proxied records targeting the Ubuntu VM. Do not delete, replace, grey-cloud, or repurpose them during the frontend cutover.
- Before changing DNS, capture the current records and define rollback values. After the approved change, verify DNS, Vercel domain status, TLS, canonical redirects, frontend loading, calls to `https://api.ladyshelf.site`, and continued public API/Harbor availability.

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
- Disposable pre-deployment test resources were deleted before the production deployment. The later production stack and `ladyshelf_postgres_data` volume are active and must not be treated as disposable.

## Repository state

- The user confirmed that all previously dirty application changes were intended for this release.
- The currently deployed backend source commit is `a7851a124b94642ba79a74df07bb7d9599890b57` from `feature/ai-product-images`. The deployment uses the immutable Harbor digest `registry.ladyshelf.site/ladyshelf/backend@sha256:59e54363e4a63e0c1e0046871507b9be6936ce81ec82e5640f44b5436ed91021`.
- Continue to inspect `git status` and targeted diffs before future edits; do not absorb new unrelated changes into deployment commits.

## Pending plan

### AI product-image rollout follow-up

- Owner browser verification of the production `/admin/catalog` AI image workflow remains required on desktop and mobile.
- The generated smoke products, generation records, and storage objects remain in production for audit. Cleanup is optional and requires a separately defined cleanup operation.
- Frontend production deployment and Vercel state should be verified separately if not already confirmed from the GitHub merge.

### 1. Post-deployment operations

- Configure or migrate Supabase JWT signing so the public JWKS endpoint exposes at least one asymmetric key, obtain a valid test-user access token without recording it, and validate a successful authenticated API request.
- Validate container restart recovery and direct-origin blocking.
- PostgreSQL backups remain explicitly declined. Do not enable the local backup timer unless the user revisits that decision; off-VM backup/restore remains strongly recommended.
- Keep SasaPay in sandbox until merchant live approval. Enable HSTS only after every intended `ladyshelf.site` hostname is permanently HTTPS-capable; start conservatively without preload/includeSubDomains.

### 2. Deferred Harbor operations

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
