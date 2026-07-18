#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${LADYSHELF_APP_DIR:-/opt/ladyshelf}"
COMPOSE_FILE="${LADYSHELF_COMPOSE_FILE:-${APP_DIR}/compose.prod.yml}"
ENV_FILE="${LADYSHELF_ENV_FILE:-${APP_DIR}/secrets/backend.env}"
BACKUP_DIR="${LADYSHELF_BACKUP_DIR:-${APP_DIR}/backups}"
RETENTION_DAYS="${LADYSHELF_BACKUP_RETENTION_DAYS:-14}"
PROJECT_NAME="${LADYSHELF_COMPOSE_PROJECT_NAME:-ladyshelf}"

test -f "${COMPOSE_FILE}"
test -f "${ENV_FILE}"
install -d -m 0700 "${BACKUP_DIR}"

umask 077
timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
target="${BACKUP_DIR}/wahi-${timestamp}.dump"
partial="${target}.partial"
trap 'rm -f -- "${partial}"' EXIT

docker compose --project-name "${PROJECT_NAME}" --env-file "${ENV_FILE}" -f "${COMPOSE_FILE}" \
    exec -T db sh -c 'pg_dump --username="$POSTGRES_USER" --dbname="$POSTGRES_DB" --format=custom' \
    > "${partial}"

test -s "${partial}"
mv "${partial}" "${target}"
trap - EXIT

find "${BACKUP_DIR}" -maxdepth 1 -type f -name 'wahi-*.dump' -mtime "+${RETENTION_DAYS}" -delete
echo "Created ${target}"
