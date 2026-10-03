#!/usr/bin/env bash
set -euo pipefail

APP_DIR="/opt/ladyshelf"
ENV_FILE="${APP_DIR}/secrets/backend.env"
COMPOSE_FILE="${APP_DIR}/compose.prod.yml"
RELEASE_SCRIPT="${APP_DIR}/scripts/release.sh"
PROJECT_NAME="ladyshelf"

usage() {
    printf 'Usage: %s <image-ref> <migration-flag:true|false>\n' "$0" >&2
    printf 'Example: %s registry.ladyshelf.site/ladyshelf/backend@sha256:<64-hex-digest> false\n' "$0" >&2
}

if (( $# != 2 )); then
    printf 'Error: expected exactly 2 arguments; received %d.\n' "$#" >&2
    usage
    exit 64
fi

image="$1"
migration_flag="$2"

if [[ ! "$image" =~ ^registry\.ladyshelf\.site/ladyshelf/backend@sha256:[a-f0-9]{64}$ ]]; then
    echo "Refusing invalid backend image reference: ${image}" >&2
    exit 65
fi

test -f "${ENV_FILE}"
test -f "${COMPOSE_FILE}"
test -x "${RELEASE_SCRIPT}"

echo "Pulling backend image before changing production config..."
docker pull "${image}"

# backup to r2 before changing production config when migrations are present.
case "$migration_flag" in
    true)
        echo "Migration changes detected; creating and verifying R2 backup..."
        /opt/ladyshelf/scripts/r2-db-backup.sh
        ;;
    false)
        echo "No migration changes detected; skipping R2 backup"
        ;;
    *)
        printf 'Error: migration flag must be true or false; received "%s".\n' "$migration_flag" >&2
        usage
        exit 64
        ;;
esac

timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
backup="${ENV_FILE}.pre-deploy-${timestamp}"

echo "Backing up environment file to ${backup}"
cp --preserve=mode,ownership,timestamps "${ENV_FILE}" "${backup}"

tmp="$(mktemp)"
trap 'rm -f -- "${tmp}"' EXIT

awk -v image="${image}" '
BEGIN { replaced = 0 }
/^BACKEND_IMAGE=/ {
    print "BACKEND_IMAGE=" image
    replaced = 1
    next
}
{ print }
END {
    if (replaced != 1) {
        exit 1
    }
}
' "${ENV_FILE}" > "${tmp}"

chown root:root "${tmp}"
chmod 0600 "${tmp}"
mv "${tmp}" "${ENV_FILE}"
trap - EXIT

echo "Updated BACKEND_IMAGE to:"
grep '^BACKEND_IMAGE=' "${ENV_FILE}"

echo "Running production release..."
"${RELEASE_SCRIPT}"

echo
echo "Deployment evidence:"
echo "Configured image:"
grep '^BACKEND_IMAGE=' "${ENV_FILE}"

echo
echo "Compose state:"
docker compose \
    --project-name "${PROJECT_NAME}" \
    --env-file "${ENV_FILE}" \
    -f "${COMPOSE_FILE}" \
    ps

echo
echo "Local health:"
curl --fail --silent --show-error \
    --header "Host: api.ladyshelf.site" \
    --header "X-Forwarded-Proto: https" \
    http://127.0.0.1:8000/api/v1/health

echo
echo
echo "Rollback hint:"
echo "To roll back the env file only:"
echo "  cp ${backup} ${ENV_FILE}"
echo "Then rerun:"
echo "  ${RELEASE_SCRIPT}"