#!/usr/bin/env bash
set -euo pipefail

REGISTRY="registry.ladyshelf.site"
IMAGE="${REGISTRY}/ladyshelf/harbor-smoke:v2.15.1"
DENIED_IMAGE="${REGISTRY}/ladyshelf/harbor-smoke:pull-only-denied"
CREDENTIAL_DIR="/opt/harbor/credentials"

set +u
source "${CREDENTIAL_DIR}/ladyshelf-publisher.env"
set -u
printf '%s' "${HARBOR_PASSWORD}" | docker login "${REGISTRY}" --username "${HARBOR_USERNAME}" --password-stdin
docker tag goharbor/harbor-portal:v2.15.1 "${IMAGE}"
docker push "${IMAGE}"
docker logout "${REGISTRY}"

docker image rm "${IMAGE}"

unset HARBOR_USERNAME HARBOR_PASSWORD
set +u
source "${CREDENTIAL_DIR}/ladyshelf-production-pull.env"
set -u
printf '%s' "${HARBOR_PASSWORD}" | docker login "${REGISTRY}" --username "${HARBOR_USERNAME}" --password-stdin
docker pull "${IMAGE}"

denied_log="$(mktemp)"
docker tag "${IMAGE}" "${DENIED_IMAGE}"
if docker push "${DENIED_IMAGE}" >"${denied_log}" 2>&1; then
    echo "Pull-only robot unexpectedly pushed an image" >&2
    docker image rm "${DENIED_IMAGE}" >/dev/null 2>&1 || true
    rm -f "${denied_log}"
    exit 1
fi
if ! grep -Eqi 'denied|unauthorized|insufficient_scope' "${denied_log}"; then
    echo "Pull-only robot push failed for an unexpected reason" >&2
    sed -n '1,20p' "${denied_log}" >&2
    docker image rm "${DENIED_IMAGE}" >/dev/null 2>&1 || true
    rm -f "${denied_log}"
    exit 1
fi
docker image rm "${DENIED_IMAGE}" >/dev/null
rm -f "${denied_log}"

docker image inspect --format 'pulled_digest={{index .RepoDigests 0}}' "${IMAGE}"
echo "Publisher push, production pull, and production push denial validated."
