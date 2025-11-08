#!/usr/bin/env bash
# DebGPT vector DB bootstrapper
#
# This script installs Qdrant from the official GitHub release artifacts, ensures the
# systemd service is enabled, and aligns DebGPT's vector-service configuration
# to talk to the local instance.  Run as root on Debian/Ubuntu systems after
# installing the debgpt/debgpt-vector-service packages.

set -euo pipefail

if [[ "${EUID}" -ne 0 ]]; then
  echo "[ERROR] Please run this script as root (use sudo)." >&2
  exit 1
fi

if ! dpkg-query -W -f='${Status}' debgpt 2>/dev/null | grep -q "install ok installed"; then
  echo "[ERROR] debgpt package not installed/configured; aborting vector DB bootstrap." >&2
  dpkg --audit || true
  exit 2
fi

if ! dpkg-query -W -f='${Status}' debgpt-vector-service 2>/dev/null | grep -q "install ok installed"; then
  echo "[ERROR] debgpt-vector-service package is not fully installed; aborting vector DB bootstrap." >&2
  dpkg --audit || true
  exit 2
fi

VECTOR_ENV="/etc/debgpt/vector-service.env"
QDRANT_URL="http://127.0.0.1:6333"
SKIP_SYSTEMCTL="${SKIP_SYSTEMCTL:-0}"
QDRANT_INSTALLED=0
STATUS_MARKER="/tmp/debgpt-qdrant-status"
QDRANT_REPO="${QDRANT_REPO:-qdrant/qdrant}"
QDRANT_VERSION="${QDRANT_VERSION:-}"
QDRANT_DEB_URL="${QDRANT_DEB_URL:-}"

install_qdrant() {
  local repo="${QDRANT_REPO}"
  local tag="${QDRANT_VERSION}"
  local url="${QDRANT_DEB_URL}"

  if [[ -z "${url}" ]]; then
    if [[ -z "${tag}" ]]; then
      echo "[*] Fetching latest Qdrant release tag from GitHub..."
      tag=$(curl -fsSL "https://api.github.com/repos/${repo}/releases/latest" \
        | grep -Po '"tag_name": "\K.*?(?=")' | head -n1)
      if [[ -z "${tag}" ]]; then
        echo "[WARN] Unable to determine latest Qdrant release; defaulting to v1.15.5." >&2
        tag="v1.15.5"
      fi
    else
      tag="v${tag#v}"
    fi
    local version="${tag#v}"
    local pkg="qdrant_${version}-1_amd64.deb"
    url="https://github.com/${repo}/releases/download/${tag}/${pkg}"
    echo "[+] Selected Qdrant release tag: ${tag}"
  fi

  echo "[*] Downloading Qdrant package from ${url}..."
  TMP_DEB="$(mktemp /tmp/qdrant-XXXXXXXX.deb)"
  if curl -fsSL "${url}" -o "${TMP_DEB}"; then
    echo "[*] Installing qdrant via dpkg..."
    if dpkg -i "${TMP_DEB}"; then
      apt-get install -fy
      QDRANT_INSTALLED=1
    else
      echo "[WARN] dpkg failed to install ${url##*/}." >&2
      QDRANT_INSTALLED=0
    fi
  else
    echo "[WARN] Unable to download Qdrant from ${url}." >&2
    QDRANT_INSTALLED=0
  fi
  rm -f "${TMP_DEB:-}"
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

  if [[ "${QDRANT_INSTALLED}" == "1" ]] && command -v systemctl >/dev/null 2>&1 && systemctl list-unit-files >/dev/null 2>&1; then
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

  echo "[WARN] systemd is unavailable or Qdrant is not installed; attempting manual startup instead." >&2
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

  local env_file="/etc/debgpt/vector-service.env"
  echo "[*] Ensuring DebGPT vector service is running..."
  if pgrep -f 'debgpt.vector_service.__main__' >/dev/null 2>&1; then
    echo "[+] DebGPT vector service already running; skipping manual start."
    return
  fi

  install -d -o debgpt -g debgpt /var/log/debgpt
  local launch_script="/tmp/debgpt-vector-manual-start.sh"
  cat >"${launch_script}" <<'EOF'
#!/bin/sh
set -e
set -a
[ -r /etc/debgpt/vector-service.env ] && . /etc/debgpt/vector-service.env
set +a
export PYTHONPATH=/usr/lib/debgpt/vector-service/site-packages
cd /usr/lib/debgpt || exit 1
nohup /usr/bin/python3 -m debgpt.vector_service.__main__ >> /var/log/debgpt/vector-service.log 2>&1 &
EOF
  chown debgpt:debgpt "${launch_script}"
  chmod 0750 "${launch_script}"

  if command -v runuser >/dev/null 2>&1; then
    if runuser -u debgpt -- "${launch_script}"; then
      sleep 2
    else
      echo "[WARN] runuser failed to launch the vector service." >&2
    fi
  else
    if su -s /bin/sh debgpt -c "${launch_script}"; then
      sleep 2
    else
      echo "[WARN] su failed to launch the vector service." >&2
    fi
  fi

  rm -f "${launch_script}"

  if pgrep -f 'debgpt.vector_service.__main__' >/dev/null 2>&1; then
    echo "[+] DebGPT vector service manual launch succeeded."
  else
    echo "[WARN] Unable to confirm DebGPT vector service is running." >&2
  fi
}

install_qdrant
configure_vector_env
restart_services

if [[ "${QDRANT_INSTALLED}" == "1" ]]; then
  echo "[DONE] Qdrant is installed and DebGPT vector service is bound to ${QDRANT_URL}."
  echo "      Validate with: curl http://127.0.0.1:8000/healthz"
  echo "installed" > "${STATUS_MARKER}"
else
  echo "[WARN] Qdrant was not installed; DebGPT vector service remains configured but requires a running Qdrant instance." >&2
  echo "missing" > "${STATUS_MARKER}"
fi
