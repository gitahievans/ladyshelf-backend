#!/usr/bin/env bash
set -euo pipefail

HARBOR_DIR="/opt/harbor"
CREDENTIAL_DIR="/opt/harbor/credentials"
API_URL="http://127.0.0.1:8081/api/v2.0"
admin_netrc="${CREDENTIAL_DIR}/admin.netrc"

admin_password="$(sed -n 's/^harbor_admin_password:[[:space:]]*//p' "${HARBOR_DIR}/harbor.yml")"
printf 'machine 127.0.0.1\nlogin admin\npassword %s\n' "${admin_password}" > "${admin_netrc}"
chmod 0600 "${admin_netrc}"
unset admin_password

get() {
    local path="$1"
    printf '\n--- %s ---\n' "${path}"
    curl --silent --show-error --fail --netrc-file "${admin_netrc}" "${API_URL}${path}"
    printf '\n'
}

get '/projects?name=ladyshelf'
get '/projects/ladyshelf'
get '/retentions/metadatas'
get '/system/gc/schedule'

rm -f "${admin_netrc}"
