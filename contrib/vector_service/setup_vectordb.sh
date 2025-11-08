#!/usr/bin/env bash
# DebGPT vector DB bootstrapper
#
# This script installs Qdrant from the upstream APT repository, ensures the
# systemd service is enabled, and aligns DebGPT's vector-service configuration
# to talk to the local instance.  Run as root on Debian/Ubuntu systems after
# installing the debgpt/debgpt-vector-service packages.

set -euo pipefail

if [[ "${EUID}" -ne 0 ]]; then
  echo "[ERROR] Please run this script as root (use sudo)." >&2
  exit 1
fi

KEYRING_PATH="/etc/apt/keyrings/qdrant.asc"
SOURCES_LIST="/etc/apt/sources.list.d/qdrant.list"
VECTOR_ENV="/etc/debgpt/vector-service.env"
QDRANT_URL="http://127.0.0.1:6333"
SKIP_SYSTEMCTL="${SKIP_SYSTEMCTL:-0}"

add_qdrant_repo() {
  if [[ ! -f "${KEYRING_PATH}" ]]; then
    echo "[*] Fetching Qdrant signing key..."
    mkdir -p "$(dirname "${KEYRING_PATH}")"
    curl -fsSL https://deps.qdrant.tech/deb/public.gpg -o "${KEYRING_PATH}"
    chmod 0644 "${KEYRING_PATH}"
  else
    echo "[+] Qdrant signing key already present."
  fi

  if [[ ! -f "${SOURCES_LIST}" ]]; then
    echo "[*] Adding Qdrant APT source..."
    cat <<EOF >"${SOURCES_LIST}"
deb [signed-by=${KEYRING_PATH}] https://deps.qdrant.tech/deb stable main
EOF
  else
    echo "[+] Qdrant APT source already configured."
  fi
}

install_qdrant() {
  echo "[*] Updating package lists..."
  apt-get update
  echo "[*] Installing qdrant..."
  apt-get install -y qdrant
}

configure_vector_env() {
  if [[ ! -f "${VECTOR_ENV}" ]]; then
    echo "[WARN] ${VECTOR_ENV} is missing. Ensure debgpt-vector-service is installed." >&2
    return
  fi

  echo "[*] Aligning ${VECTOR_ENV} with local Qdrant settings..."
  if grep -q '^QDRANT_URL=' "${VECTOR_ENV}"; then
    sed -i "s|^QDRANT_URL=.*$|QDRANT_URL=${QDRANT_URL}|" "${VECTOR_ENV}"
  else
    echo "QDRANT_URL=${QDRANT_URL}" >> "${VECTOR_ENV}"
  fi

  if grep -q '^QDRANT_COLLECTION=' "${VECTOR_ENV}"; then
    sed -i 's|^QDRANT_COLLECTION=.*$|QDRANT_COLLECTION=chat_messages|' "${VECTOR_ENV}"
  else
    echo "QDRANT_COLLECTION=chat_messages" >> "${VECTOR_ENV}"
  fi
}

restart_services() {
  if [[ "${SKIP_SYSTEMCTL}" == "1" ]]; then
    echo "[INFO] SKIP_SYSTEMCTL=1; skipping systemd management calls."
    fallback_startup
    return
  fi

  if command -v systemctl >/dev/null 2>&1 && systemctl list-unit-files >/dev/null 2>&1; then
    echo "[*] Enabling and starting qdrant.service..."
    if ! systemctl enable --now qdrant.service; then
      echo "[WARN] systemd failed to start qdrant.service; falling back to manual launch." >&2
      fallback_startup
      return
    fi

    if systemctl list-unit-files | grep -q '^debgpt-vector-service.service'; then
      echo "[*] Restarting debgpt-vector-service.service..."
      if ! systemctl restart debgpt-vector-service.service; then
        echo "[WARN] Unable to restart debgpt-vector-service.service via systemd." >&2
      fi
    else
      echo "[INFO] debgpt-vector-service.service not found; install debgpt-vector-service package if needed." >&2
    fi
    return
  fi

  echo "[WARN] systemd is unavailable; attempting manual startup instead." >&2
  fallback_startup
}

fallback_startup() {
  if command -v qdrant >/dev/null 2>&1; then
    echo "[*] Manually starting qdrant in the background..."
    mkdir -p /var/log/qdrant
    if pgrep -f '^qdrant' >/dev/null 2>&1; then
      echo "[+] qdrant is already running; skipping manual start."
    else
      nohup qdrant --config /etc/qdrant/config.yaml >/var/log/qdrant/standalone.log 2>&1 &
      sleep 2
      if pgrep -f '^qdrant' >/dev/null 2>&1; then
        echo "[+] qdrant standalone launch succeeded."
      else
        echo "[WARN] Unable to confirm qdrant is running." >&2
      fi
    fi
  else
    echo "[WARN] qdrant binary not found; cannot perform manual start." >&2
  fi

  echo "[INFO] If debgpt-vector-service is required, start it manually once systemd is available." >&2
}

add_qdrant_repo
install_qdrant
configure_vector_env
restart_services

echo "[DONE] Qdrant is installed and DebGPT vector service is bound to ${QDRANT_URL}."
echo "      Validate with: curl http://127.0.0.1:8000/healthz"
