# Harbor registry operations

This runbook documents the LadyShelf Harbor registry installed on the production VM. Read `AGENTS.md` before acting. VM, Cloudflare, DNS, Nginx, Docker, credential, and repository changes require explicit user approval.

## Current deployment

| Item | Value |
| --- | --- |
| Public URL | `https://registry.ladyshelf.site` |
| Harbor version | `v2.15.1` |
| Project | `ladyshelf` (private) |
| Project quota | 5 GiB |
| Harbor directory | `/opt/harbor` |
| Persistent data | `/opt/harbor-data` |
| Harbor logs | `/var/log/harbor` |
| Internal endpoint | `http://127.0.0.1:8081` |
| Public endpoint | Host Nginx on port 443 |
| Scanner | Trivy is not installed |

Initial published backend release:

- source commit: `1f3f52ba5a05bc3f59e421fa86d05da0a1eb1881`;
- tag: `registry.ladyshelf.site/ladyshelf/backend:1f3f52ba5a05bc3f59e421fa86d05da0a1eb1881`;
- immutable digest: `registry.ladyshelf.site/ladyshelf/backend@sha256:86740e767f16efd21f25b48f5e8f824eb48121b46da3d4bd99e5e904b9df99b4`;
- publisher push and production pull succeeded through Cloudflare on 2026-07-18.

The image was scanned externally with checksum-verified Trivy v0.69.3 because the integrated Harbor scanner is intentionally absent. A fixable PyJWT authentication-bypass finding was corrected before publication. The published image retained unfixed Debian base-image findings, including three critical `perl-base` records; rescan it when a new Debian/Python base image is available. The PostgreSQL-backed test suite and production checks were deliberately not rerun for this publication at the user's direction.

The initial image was superseded before public cutover because Gunicorn 26's default control socket attempted to write beneath the read-only `/app` filesystem. Current deployed backend release:

- source commit: `5273eecab837c561de800ed3fb2f04ba2bb5a74d`;
- tag: `registry.ladyshelf.site/ladyshelf/backend:5273eecab837c561de800ed3fb2f04ba2bb5a74d`;
- immutable digest: `registry.ladyshelf.site/ladyshelf/backend@sha256:57bc9291f151d6212cda66e97ad6bb0da39fccbb54a46c25c04ecc5cc6c8ed35`;
- checksum-verified scan matched the accepted prior baseline and production pull verification passed through Cloudflare on 2026-07-18.

This is an intentionally constrained deployment. The VM has 2 vCPU, 3.7 GiB RAM, and a 38 GiB root disk, below [Harbor's published minimum](https://goharbor.io/docs/edge/install-config/installation-prereqs/). Harbor shares the host with the planned Django and PostgreSQL stack. Monitor memory, swap, and disk closely; idle measurements do not predict behavior under image pushes, garbage collection, database work, or application load.

## Request path and isolation

Public registry traffic follows this path:

```text
Docker client
  -> Cloudflare proxy for registry.ladyshelf.site
  -> host Nginx on 443
  -> Harbor proxy on 127.0.0.1:8081
```

- Cloudflare DNS has a proxied A record for `registry.ladyshelf.site` pointing to `157.90.244.105`.
- Cloudflare uses Full (strict). A dedicated Origin CA ECC certificate covers only `registry.ladyshelf.site`.
- The origin certificate is `/etc/ssl/certs/registry.ladyshelf.site.pem`.
- Its private key is `/etc/ssl/private/registry.ladyshelf.site.key`, mode `0600`, root-only.
- The Nginx site is `/etc/nginx/sites-available/registry.ladyshelf.site`, enabled from `sites-enabled`.
- Harbor's generated Compose port must remain `127.0.0.1:8081:8080`. Never publish it as `8081:8080` or expose Harbor directly.
- UFW continues to allow port 443 only from Cloudflare's published networks.

Cloudflare-proxied uploads are subject to plan-specific request-size and proxy timeout limits. As verified on 2026-07-18, Cloudflare documents a [100 MB maximum upload size](https://developers.cloudflare.com/support/troubleshooting/http-status-codes/4xx-client-error/error-413/) for Free and Pro zones and separate [proxy connection timeouts](https://developers.cloudflare.com/fundamentals/reference/connection-limits/). Recheck those sources before relying on the values. Keep backend image layers below the applicable limit and validate every production image push through the public hostname.

## Files and permissions

| Path | Purpose | Required protection |
| --- | --- | --- |
| `/opt/harbor/harbor.yml` | Harbor configuration and admin/database secrets | `0600`, root-only |
| `/opt/harbor/docker-compose.yml` | Generated Harbor Compose model | root-owned; preserve loopback port patch |
| `/opt/harbor/credentials/` | Robot credential directory | `0700`, root-only |
| `/opt/harbor/credentials/ladyshelf-publisher.env` | Publisher robot credential | `0600`, root-only |
| `/opt/harbor/credentials/ladyshelf-production-pull.env` | Production pull robot credential | `0600`, root-only |
| `/opt/harbor-data` | Harbor database, registry, Redis, and secret data | root-controlled; include in backups |
| `/var/log/harbor` | Harbor logs | root-controlled |

Never commit, paste into chat, or copy into ordinary shell history any password, robot secret, private key, `harbor.yml`, credential environment file, or Docker authentication file.

## Accounts

### Web administration

- Username: `admin`
- Password source: `harbor_admin_password` in `/opt/harbor/harbor.yml`

Retrieve it only into an authorized administrator's terminal:

```powershell
ssh -i $HOME\.ssh\id_ed25519_hetzner root@157.90.244.105 'sed -n "s/^harbor_admin_password:[[:space:]]*//p" /opt/harbor/harbor.yml'
```

### Robot accounts

| Username | Scope | Intended use |
| --- | --- | --- |
| `robot$ladyshelf-publisher` | `ladyshelf`: repository pull/push | Build and publish release images |
| `robot$ladyshelf-production-pull` | `ladyshelf`: repository pull only | Pull images for production releases |

Both robots were created with 365-day lifetimes. Record and schedule rotation before expiry. The production robot has been tested to confirm that a new-tag push is denied.

Rotate both robot secrets with:

```bash
/opt/harbor/rotate-robot-secrets.sh
```

Rotation immediately invalidates the previous secrets and rewrites both root-only credential files. Coordinate the change with every legitimate consumer before running it.

## Health and status

Run these read-only checks from the VM:

```bash
cd /opt/harbor
docker compose ps
curl --fail http://127.0.0.1:8081/api/v2.0/health
curl --fail http://127.0.0.1:8081/api/v2.0/ping
ss -ltnp | grep 8081
docker stats --no-stream
df -h /
du -sh /opt/harbor-data /var/log/harbor
docker system df
```

Expected results:

- all nine Harbor containers are healthy;
- health and ping return HTTP 200;
- port 8081 listens only on `127.0.0.1`;
- no Harbor port is publicly bound;
- root disk and available memory remain within the operating thresholds below.

Public checks:

```bash
curl --fail https://registry.ladyshelf.site/api/v2.0/ping
curl --head https://registry.ladyshelf.site/v2/
```

The ping should return HTTP 200 and `Pong`. Unauthenticated `/v2/` should return HTTP 401 with a Bearer challenge whose realm is `https://registry.ladyshelf.site/service/token`.

## Capacity guardrails

Because Harbor and the future application share a below-minimum VM:

- investigate immediately if root disk usage reaches 70%;
- stop publishing new images at 80% until space is reclaimed safely;
- treat sustained swap activity, OOM kills, or less than 512 MiB available memory as an incident;
- retain immutable releases selectively rather than accumulating tags;
- never use `docker system prune`, remove Harbor volumes, or delete files beneath `/opt/harbor-data` as an ad hoc cleanup method.

At installation, root disk usage was 9.1 GiB of 38 GiB with about 27 GiB free. Harbor's idle containers used about 143 MiB combined. These are baseline measurements only.

## Docker login and image publishing

Log the VM into Harbor as the publisher without displaying the secret:

```bash
set +u
source /opt/harbor/credentials/ladyshelf-publisher.env
set -u
printf '%s' "$HARBOR_PASSWORD" | docker login registry.ladyshelf.site \
  --username "$HARBOR_USERNAME" --password-stdin
unset HARBOR_USERNAME HARBOR_PASSWORD
```

Use immutable commit-SHA tags, never `latest`:

```bash
docker tag wahi-backend:build registry.ladyshelf.site/ladyshelf/backend:<commit-sha>
docker push registry.ladyshelf.site/ladyshelf/backend:<commit-sha>
docker image inspect --format '{{index .RepoDigests 0}}' \
  registry.ladyshelf.site/ladyshelf/backend:<commit-sha>
```

Record the digest in `docs/deployment-handoff.md` and set production `BACKEND_IMAGE` to the immutable tag or digest.

For production pulls, authenticate with `ladyshelf-production-pull.env` using the same `--password-stdin` pattern. Docker stores login material in `/root/.docker/config.json`; keep that file root-only and do not copy it into the repository or image build context.

## Lifecycle operations

Harbor lifecycle commands must be run from `/opt/harbor`:

```bash
cd /opt/harbor
docker compose up -d
docker compose restart
docker compose down
```

These commands change service state and require approval. `down` interrupts registry availability but preserves bind-mounted Harbor data unless destructive volume flags or manual deletion are used. Never add `--volumes` during normal operations.

After any start, restart, host reboot, or upgrade, verify:

1. all containers become healthy;
2. loopback health and ping return HTTP 200;
3. `ss` shows only `127.0.0.1:8081` for Harbor;
4. public ping and registry authentication work through Cloudflare;
5. memory, swap, disk, and recent logs show no regression.

Restart-survival validation has not yet been completed for this installation. It was explicitly deferred on 2026-07-18 so the first application release could proceed; normal push/pull smoke testing has passed, but reboot recovery remains unverified.

## Logs and troubleshooting

```bash
cd /opt/harbor
docker compose logs --tail=200
docker logs harbor-core --since 15m
tail -n 200 /var/log/nginx/registry.ladyshelf.site.error.log
tail -n 200 /var/log/nginx/registry.ladyshelf.site.access.log
```

Common symptoms:

- `401 Unauthorized` from `/v2/` without credentials is expected.
- `401` after `docker login` usually means the robot secret is stale, expired, or mismatched with its root-only credential file.
- `403`, `denied`, or `insufficient_scope` while pushing with the production robot is expected; use the publisher robot.
- Cloudflare `413` indicates a request exceeded the plan upload limit. Rebuild the image with smaller layers rather than bypassing Cloudflare without a new architecture approval.
- Cloudflare `524` can indicate a proxy timeout. Inspect Nginx and Harbor logs and measure the layer transfer before changing timeouts or network design.
- `502` or `503` on the registry hostname requires checking Harbor health, the loopback listener, and the registry Nginx error log.
- A public 526 indicates an Origin CA hostname, expiry, or Full (strict) validation problem.

Harbor logs are configured to rotate at 20 MiB with five retained files.

## Retention and garbage collection

The project quota is active, but tag-retention and scheduled garbage-collection policies are not yet configured. A read-only API inspection on 2026-07-18 confirmed that neither policy existed, and no maintenance policy was applied during that session.

The user approved a future policy that keeps the five most recently pushed tags per repository and weekly garbage collection with one worker, but then explicitly deferred its implementation to prioritize shipping. Return to this work after the first application release:

1. configure retention to keep the five most recently pushed tags per repository, while first confirming that the active production and rollback digests remain protected;
2. schedule garbage collection during a low-traffic window with one worker;
3. run an initial dry run and review its output;
4. verify disk usage after the first real collection;
5. record the policy and evidence in `docs/deployment-handoff.md`.

Deleting tags does not immediately reclaim blob storage. Garbage collection is required. Never run destructive cleanup without first identifying the active production and rollback digests.

## Backup and restore

An off-VM Harbor backup is not configured. The user explicitly chose on 2026-07-18 not to perform this work before the first application release. Harbor data on the VM root disk does not survive total VM or disk loss, so images and metadata must be considered rebuild-only until recovery is implemented and tested.

A complete Harbor backup design must include:

- `/opt/harbor/harbor.yml` and the exact Harbor version;
- `/opt/harbor-data`, captured with Harbor quiesced or using a Harbor-supported consistent procedure;
- `/etc/nginx/sites-available/registry.ladyshelf.site`;
- the Origin CA certificate and separately protected private key;
- root-only robot credential files or a planned robot-secret rotation after restore;
- an encrypted off-VM destination with retention and a tested restore procedure.

Do not claim Harbor is recoverable until a backup has been copied off the VM, restored into an isolated environment, and validated with login, pull, and representative metadata checks.

## Upgrade procedure

Do not rerun `install-constrained.sh` on the installed instance; it intentionally refuses to overwrite an existing `harbor.yml`.

For a future Harbor upgrade:

1. read the release-specific Harbor upgrade and migration notes;
2. confirm the target version's resource requirements;
3. take and verify an off-VM backup;
4. record current image digests, configuration, health, and free capacity;
5. download the official installer and verify its signature and published digest;
6. migrate the configuration using Harbor's supported upgrade process;
7. regenerate the Compose model;
8. reapply and verify the loopback-only `127.0.0.1:8081:8080` binding before startup;
9. validate health, authentication, push/pull authorization, Nginx, Cloudflare, resource usage, and rollback readiness;
10. update `docs/deployment-handoff.md`.

Do not upgrade Harbor at the same time as a Django or PostgreSQL release.

## Repository helpers

The non-secret helpers under `deploy/harbor/` mirror the installed operational scripts:

- `install-constrained.sh`: first-install configuration generation and loopback binding enforcement;
- `configure-instance.sh`: first-time private project and robot creation;
- `rotate-robot-secrets.sh`: coordinated robot-secret rotation;
- `smoke-test.sh`: publisher push, production pull, and production push-denial validation;
- `nginx-registry.conf`: registry Nginx virtual host.

The first-install and instance-configuration helpers are not general-purpose idempotent reconcilers. Review their preconditions before use.
