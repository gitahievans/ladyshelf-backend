#!/usr/bin/env bash
set -euo pipefail

# This deployment intentionally runs Harbor below its published minimum sizing.
# Keep the service loopback-only and use the host Nginx as its public endpoint.

HARBOR_DIR="/opt/harbor"
HARBOR_DATA_DIR="/opt/harbor-data"
HARBOR_LOG_DIR="/var/log/harbor"
HARBOR_HOSTNAME="registry.ladyshelf.site"
HARBOR_LOOPBACK_PORT="8081"

if [[ ! -x "${HARBOR_DIR}/prepare" || ! -f "${HARBOR_DIR}/harbor.yml.tmpl" ]]; then
    echo "Verified Harbor installer is not present in ${HARBOR_DIR}" >&2
    exit 1
fi

if [[ -e "${HARBOR_DIR}/harbor.yml" ]]; then
    echo "Refusing to overwrite existing ${HARBOR_DIR}/harbor.yml" >&2
    exit 1
fi

install -d -m 0700 "${HARBOR_DATA_DIR}" "${HARBOR_LOG_DIR}"
install -m 0600 "${HARBOR_DIR}/harbor.yml.tmpl" "${HARBOR_DIR}/harbor.yml"

admin_password="$(openssl rand -hex 32)"
database_password="$(openssl rand -hex 32)"

sed -i \
    -e "s/^hostname:.*/hostname: ${HARBOR_HOSTNAME}/" \
    -e "0,/^  port: 80$/s//  port: ${HARBOR_LOOPBACK_PORT}/" \
    -e '/^https:/,/^# # Harbor/{s/^/# /}' \
    -e "s|^# external_url:.*|external_url: https://${HARBOR_HOSTNAME}|" \
    -e "s/^harbor_admin_password:.*/harbor_admin_password: ${admin_password}/" \
    -e "s/^  password: root123$/  password: ${database_password}/" \
    -e 's/^  max_idle_conns: 100$/  max_idle_conns: 5/' \
    -e 's/^  max_open_conns: 900$/  max_open_conns: 20/' \
    -e "s|^data_volume: /data$|data_volume: ${HARBOR_DATA_DIR}|" \
    -e 's/^  max_job_workers: 10$/  max_job_workers: 2/' \
    -e 's/^    rotate_count: 50$/    rotate_count: 5/' \
    -e 's/^    rotate_size: 200M$/    rotate_size: 20M/' \
    -e "s|^    location: /var/log/harbor$|    location: ${HARBOR_LOG_DIR}|" \
    "${HARBOR_DIR}/harbor.yml"

unset admin_password database_password

cd "${HARBOR_DIR}"
./prepare

# Harbor's generated Compose file publishes on all interfaces by default.
# Pin its only host port to loopback so Docker cannot bypass UFW.
sed -i \
    -e "s/- ${HARBOR_LOOPBACK_PORT}:8080/- 127.0.0.1:${HARBOR_LOOPBACK_PORT}:8080/" \
    -e "s/\"${HARBOR_LOOPBACK_PORT}:8080\"/\"127.0.0.1:${HARBOR_LOOPBACK_PORT}:8080\"/" \
    -e "s/'${HARBOR_LOOPBACK_PORT}:8080'/'127.0.0.1:${HARBOR_LOOPBACK_PORT}:8080'/" \
    "${HARBOR_DIR}/docker-compose.yml"

if ! grep -Fq "127.0.0.1:${HARBOR_LOOPBACK_PORT}:8080" "${HARBOR_DIR}/docker-compose.yml"; then
    echo "Failed to constrain Harbor's published port to loopback" >&2
    exit 1
fi

chmod 0600 "${HARBOR_DIR}/harbor.yml"
echo "Harbor configuration prepared with loopback-only publishing."
