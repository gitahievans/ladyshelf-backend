#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${LADYSHELF_APP_DIR:-/opt/ladyshelf}"
COMPOSE_FILE="${LADYSHELF_COMPOSE_FILE:-${APP_DIR}/compose.prod.yml}"
ENV_FILE="${LADYSHELF_ENV_FILE:-${APP_DIR}/secrets/backend.env}"
PROJECT_NAME="${LADYSHELF_COMPOSE_PROJECT_NAME:-ladyshelf}"

test -f "${COMPOSE_FILE}"
test -f "${ENV_FILE}"

compose=(docker compose --project-name "${PROJECT_NAME}" --env-file "${ENV_FILE}" -f "${COMPOSE_FILE}")

"${compose[@]}" config --quiet
"${compose[@]}" pull
"${compose[@]}" up -d db
"${compose[@]}" run --rm backend python manage.py migrate --noinput
"${compose[@]}" run --rm backend python manage.py bootstrap_admin_roles
"${compose[@]}" up -d --remove-orphans

curl --fail --silent --show-error \
    --retry 12 --retry-delay 5 --retry-all-errors \
    --header "Host: api.ladyshelf.site" \
    --header "X-Forwarded-Proto: https" \
    http://127.0.0.1:8000/api/v1/health

echo
"${compose[@]}" ps
