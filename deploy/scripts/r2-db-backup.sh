#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${LADYSHELF_APP_DIR:-/opt/ladyshelf}"
COMPOSE_FILE="${LADYSHELF_COMPOSE_FILE:-${APP_DIR}/compose.prod.yml}"
ENV_FILE="${LADYSHELF_ENV_FILE:-${APP_DIR}/secrets/backend.env}"
BACKUP_DIR="${LADYSHELF_BACKUP_DIR:-${APP_DIR}/backups}"
RETENTION_DAYS="${LADYSHELF_BACKUP_RETENTION_DAYS:-1}"
PROJECT_NAME="${LADYSHELF_COMPOSE_PROJECT_NAME:-ladyshelf}"

test -f "${COMPOSE_FILE}"
test -f "${ENV_FILE}"

# Changed: read only specific required values from the env file instead of sourcing all secrets.
get_env_value() {
    local key="$1"

    awk -F= -v key="${key}" '
        $1 == key {
            print substr($0, index($0, "=") + 1)
            found = 1
            exit
        }
        END {
            if (!found) exit 1
        }
    ' "${ENV_FILE}"
}

# Changed: make required config failures explicit and friendly.
require_env_value() {
    local key="$1"
    local value

    value="$(get_env_value "${key}")" || {
        echo "Error: ${key} is missing from ${ENV_FILE}" >&2
        exit 1
    }

    if [ -z "${value}" ]; then
        echo "Error: ${key} is empty in ${ENV_FILE}" >&2
        exit 1
    fi

    printf '%s' "${value}"
}

DUMP_ENCRYPTION_KEY="$(require_env_value R2_DUMP_PUBLIC_ENCRYPTION_KEY)"
R2_ACCOUNT_ID="$(require_env_value R2_ACCOUNT_ID)"
R2_BACKUP_BUCKET="$(require_env_value R2_BACKUP_BUCKET)"
R2_ACCESS_KEY_ID="$(require_env_value R2_ACCESS_KEY_ID)"
R2_SECRET_ACCESS_KEY="$(require_env_value R2_SECRET_ACCESS_KEY)"

# Changed: derive the R2 endpoint from account ID so there is one clear source of truth.
R2_ENDPOINT_URL="https://${R2_ACCOUNT_ID}.r2.cloudflarestorage.com"

if [[ ! "${DUMP_ENCRYPTION_KEY}" == age1* ]]; then
    echo "Error: R2_DUMP_PUBLIC_ENCRYPTION_KEY does not look like an age public key" >&2
    exit 1
fi

install -d -m 0700 "${BACKUP_DIR}"
umask 077

timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
target="${BACKUP_DIR}/ladyshelf-${timestamp}.dump"
partial="${target}.partial"
encrypted_target="${BACKUP_DIR}/ladyshelf-r2-${timestamp}.dump.age"
partial_encrypted_target="${encrypted_target}.partial"

# Changed: define one remote object key and reuse it for upload and verification.
remote_object_key="prod/postgres/$(date -u +%Y/%m/%d)/$(basename "${encrypted_target}")"

cleanup_partials() {
    rm -f -- "${partial}" "${partial_encrypted_target}"
}
trap cleanup_partials EXIT

verify_dump_file() {
    local dump_file="$1"

    if [ ! -s "${dump_file}" ]; then
        echo "Error: dump file is missing or empty: ${dump_file}" >&2
        return 1
    fi

    local toc
    if ! toc=$(docker compose --project-name "${PROJECT_NAME}" --env-file "${ENV_FILE}" -f "${COMPOSE_FILE}" \
        exec -T db pg_restore --list < "${dump_file}" 2>&1); then
        echo "Error: pg_restore could not read dump as a valid archive:" >&2
        echo "${toc}" >&2
        return 1
    fi

    local table_count
    table_count="$(printf '%s\n' "${toc}" | awk '/ TABLE / { count++ } END { print count + 0 }')"

    if [ "${table_count}" -eq 0 ]; then
        echo "Error: dump contains no TABLE entries; likely an empty or broken backup" >&2
        return 1
    fi

    echo "Dump verified: ${table_count} table entries found in TOC"
}

docker compose --project-name "${PROJECT_NAME}" --env-file "${ENV_FILE}" -f "${COMPOSE_FILE}" \
    exec -T db sh -c 'pg_dump --username="$POSTGRES_USER" --dbname="$POSTGRES_DB" --format=custom' \
    > "${partial}"

verify_dump_file "${partial}"

age -r "${DUMP_ENCRYPTION_KEY}" -o "${partial_encrypted_target}" "${partial}"
test -s "${partial_encrypted_target}"

mv "${partial}" "${target}"
mv "${partial_encrypted_target}" "${encrypted_target}"

trap - EXIT

echo "Created local dump: ${target}"
echo "Created encrypted dump: ${encrypted_target}"

# Changed: pass AWS CLI credentials only to the upload/check commands.
# Changed: upload to the exact remote key we will verify later.
AWS_ACCESS_KEY_ID="${R2_ACCESS_KEY_ID}" \
AWS_SECRET_ACCESS_KEY="${R2_SECRET_ACCESS_KEY}" \
AWS_EC2_METADATA_DISABLED=true \
aws s3 cp \
    "${encrypted_target}" \
    "s3://${R2_BACKUP_BUCKET}/${remote_object_key}" \
    --endpoint-url "${R2_ENDPOINT_URL}"

echo "Uploaded encrypted dump to R2 ✅: s3://${R2_BACKUP_BUCKET}/${remote_object_key}"

# Changed: verify the exact object key and fail loudly if it is missing.
AWS_ACCESS_KEY_ID="${R2_ACCESS_KEY_ID}" \
AWS_SECRET_ACCESS_KEY="${R2_SECRET_ACCESS_KEY}" \
AWS_EC2_METADATA_DISABLED=true \
aws s3api head-object \
    --bucket "${R2_BACKUP_BUCKET}" \
    --key "${remote_object_key}" \
    --endpoint-url "${R2_ENDPOINT_URL}" \
    >/dev/null

echo "Verified R2 object exists ✅: s3://${R2_BACKUP_BUCKET}/${remote_object_key}"

# Changed: retention runs after the current backup has been created, uploaded, and verified.
find "${BACKUP_DIR}" -maxdepth 1 -type f -name 'ladyshelf-*.dump' -mtime "+${RETENTION_DAYS}" -delete
find "${BACKUP_DIR}" -maxdepth 1 -type f -name 'ladyshelf-r2-*.dump.age' -mtime "+${RETENTION_DAYS}" -delete