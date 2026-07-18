#!/usr/bin/env bash
set -euo pipefail

HARBOR_DIR="/opt/harbor"
CREDENTIAL_DIR="/opt/harbor/credentials"
API_URL="http://127.0.0.1:8081/api/v2.0"

admin_password="$(sed -n 's/^harbor_admin_password:[[:space:]]*//p' "${HARBOR_DIR}/harbor.yml")"
admin_netrc="${CREDENTIAL_DIR}/admin.netrc"
robot_list="${CREDENTIAL_DIR}/robot-list.json"

printf 'machine 127.0.0.1\nlogin admin\npassword %s\n' "${admin_password}" > "${admin_netrc}"
chmod 0600 "${admin_netrc}"
unset admin_password

curl --silent --show-error --fail \
    --netrc-file "${admin_netrc}" \
    "${API_URL}/robots?page_size=100" > "${robot_list}"
chmod 0600 "${robot_list}"

rotate_robot() {
    local short_name="$1"
    local expected_name="robot\$${short_name}"
    local robot_id request response status returned_secret credential_file

    robot_id="$(python3 -c 'import json,sys; data=json.load(open(sys.argv[1])); print(next((str(item["id"]) for item in data if item.get("name")==sys.argv[2]), ""))' "${robot_list}" "${expected_name}")"
    if [[ -z "${robot_id}" ]]; then
        echo "Robot ${expected_name} was not found" >&2
        exit 1
    fi

    request="${CREDENTIAL_DIR}/${short_name}-rotate-request.json"
    response="${CREDENTIAL_DIR}/${short_name}-rotate-response.json"
    credential_file="${CREDENTIAL_DIR}/${short_name}.env"
    printf '{}\n' > "${request}"
    chmod 0600 "${request}"

    status="$(curl --silent --show-error --output "${response}" --write-out '%{http_code}' \
        --request PATCH \
        --netrc-file "${admin_netrc}" \
        --header 'Content-Type: application/json' \
        --data-binary "@${request}" \
        "${API_URL}/robots/${robot_id}")"
    if [[ "${status}" != "200" ]]; then
        echo "Robot ${expected_name} secret rotation returned HTTP ${status}" >&2
        exit 1
    fi

    returned_secret="$(sed -n 's/.*"secret":[[:space:]]*"\([^"]*\)".*/\1/p' "${response}")"
    if [[ -z "${returned_secret}" ]]; then
        echo "Unable to read rotated secret for ${expected_name}" >&2
        exit 1
    fi

    printf "HARBOR_USERNAME='%s'\nHARBOR_PASSWORD='%s'\n" "${expected_name}" "${returned_secret}" > "${credential_file}"
    chmod 0600 "${credential_file}"
    rm -f "${request}" "${response}"
    unset returned_secret
}

rotate_robot "ladyshelf-publisher"
rotate_robot "ladyshelf-production-pull"

rm -f "${admin_netrc}" "${robot_list}"
echo "Robot secrets rotated and root-only credential files updated."
