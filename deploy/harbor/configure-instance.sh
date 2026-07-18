#!/usr/bin/env bash
set -euo pipefail

HARBOR_DIR="/opt/harbor"
CREDENTIAL_DIR="/opt/harbor/credentials"
API_URL="http://127.0.0.1:8081/api/v2.0"
PROJECT_NAME="ladyshelf"
PROJECT_QUOTA_BYTES="5368709120"
ROBOT_DURATION_DAYS="365"

install -d -m 0700 "${CREDENTIAL_DIR}"

admin_password="$(sed -n 's/^harbor_admin_password:[[:space:]]*//p' "${HARBOR_DIR}/harbor.yml")"
if [[ -z "${admin_password}" ]]; then
    echo "Unable to read Harbor admin credential" >&2
    exit 1
fi

admin_netrc="${CREDENTIAL_DIR}/admin.netrc"
printf 'machine 127.0.0.1\nlogin admin\npassword %s\n' "${admin_password}" > "${admin_netrc}"
chmod 0600 "${admin_netrc}"
unset admin_password

project_request="${CREDENTIAL_DIR}/project-request.json"
printf '{"project_name":"%s","public":false,"storage_limit":%s}\n' \
    "${PROJECT_NAME}" "${PROJECT_QUOTA_BYTES}" > "${project_request}"
chmod 0600 "${project_request}"

status="$(curl --silent --show-error --output /dev/null --write-out '%{http_code}' \
    --netrc-file "${admin_netrc}" \
    --header 'Content-Type: application/json' \
    --data-binary "@${project_request}" \
    "${API_URL}/projects")"
if [[ "${status}" != "201" ]]; then
    echo "Project creation returned HTTP ${status}" >&2
    exit 1
fi
rm -f "${project_request}"

create_robot() {
    local short_name="$1"
    local description="$2"
    local access_json="$3"
    local secret returned_secret request response status full_name credential_file

    secret="$(openssl rand -hex 32)"
    request="${CREDENTIAL_DIR}/${short_name}-request.json"
    response="${CREDENTIAL_DIR}/${short_name}-response.json"
    credential_file="${CREDENTIAL_DIR}/${short_name}.env"

    printf '{"name":"%s","description":"%s","secret":"%s","level":"system","disable":false,"duration":%s,"permissions":[{"kind":"project","namespace":"%s","access":%s}]}\n' \
        "${short_name}" "${description}" "${secret}" "${ROBOT_DURATION_DAYS}" \
        "${PROJECT_NAME}" "${access_json}" > "${request}"
    chmod 0600 "${request}"

    status="$(curl --silent --show-error --output "${response}" --write-out '%{http_code}' \
        --netrc-file "${admin_netrc}" \
        --header 'Content-Type: application/json' \
        --data-binary "@${request}" \
        "${API_URL}/robots")"
    if [[ "${status}" != "201" ]]; then
        echo "Robot ${short_name} creation returned HTTP ${status}" >&2
        exit 1
    fi

    full_name="$(sed -n 's/.*"name":[[:space:]]*"\([^"]*\)".*/\1/p' "${response}")"
    if [[ -z "${full_name}" ]]; then
        echo "Unable to read created robot name for ${short_name}" >&2
        exit 1
    fi

    returned_secret="$(sed -n 's/.*"secret":[[:space:]]*"\([^"]*\)".*/\1/p' "${response}")"
    if [[ -z "${returned_secret}" ]]; then
        echo "Unable to read created robot secret for ${short_name}" >&2
        exit 1
    fi

    printf "HARBOR_USERNAME='%s'\nHARBOR_PASSWORD='%s'\n" "${full_name}" "${returned_secret}" > "${credential_file}"
    chmod 0600 "${credential_file}"
    rm -f "${request}" "${response}"
    unset secret returned_secret full_name
}

create_robot \
    "ladyshelf-publisher" \
    "Push and pull LadyShelf release images" \
    '[{"resource":"repository","action":"pull","effect":"allow"},{"resource":"repository","action":"push","effect":"allow"}]'

create_robot \
    "ladyshelf-production-pull" \
    "Pull LadyShelf release images on the production VM" \
    '[{"resource":"repository","action":"pull","effect":"allow"}]'

rm -f "${admin_netrc}"
echo "Private project and scoped robot accounts created."
