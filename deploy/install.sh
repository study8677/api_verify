#!/usr/bin/env bash
# Idempotent installer for apiverify.aidcmo.com on the NY server.
# Run as root from /opt/api-verify (a checkout of github.com/study8677/api_verify).
set -euo pipefail

APP_DIR=/opt/api-verify
VENV=${APP_DIR}/.venv
SVC=api-verify.service
RUNUSER=apiverify

if [[ "${EUID}" -ne 0 ]]; then
    echo "must run as root" >&2
    exit 1
fi

cd "${APP_DIR}"

echo "==> system user ${RUNUSER}"
if ! id -u "${RUNUSER}" >/dev/null 2>&1; then
    useradd --system --no-create-home --shell /usr/sbin/nologin "${RUNUSER}"
fi

echo "==> python venv"
if [[ ! -d "${VENV}" ]]; then
    python3 -m venv "${VENV}"
fi
"${VENV}/bin/pip" install --upgrade pip --quiet
"${VENV}/bin/pip" install --upgrade -e ".[web]" --quiet

echo "==> ownership"
# venv + repo must be readable by the runtime user; writes are not needed.
chown -R root:${RUNUSER} "${APP_DIR}"
find "${APP_DIR}" -type d -exec chmod 0755 {} +
find "${APP_DIR}" -type f -exec chmod 0644 {} +
chmod 0755 "${APP_DIR}/deploy/install.sh"
# venv contains executables that need the +x bit preserved
find "${VENV}/bin" -type f -exec chmod 0755 {} + 2>/dev/null || true

echo "==> systemd unit"
install -m 0644 deploy/api-verify.service /etc/systemd/system/${SVC}
systemctl daemon-reload
systemctl enable --now ${SVC}
systemctl restart ${SVC}
sleep 2
systemctl --no-pager --lines=5 status ${SVC} || true

echo "==> nginx site"
install -m 0644 deploy/nginx-apiverify.conf /etc/nginx/sites-available/apiverify.aidcmo.com.conf
ln -sf /etc/nginx/sites-available/apiverify.aidcmo.com.conf /etc/nginx/sites-enabled/apiverify.aidcmo.com.conf
nginx -t
systemctl reload nginx

echo "==> health probe"
curl -fsS http://127.0.0.1:8083/api/health && echo

echo "==> done."
echo "Next steps:"
echo "  1. Confirm DNS A record: apiverify.aidcmo.com -> server IP"
echo "  2. Issue TLS cert:        certbot --nginx -d apiverify.aidcmo.com"
