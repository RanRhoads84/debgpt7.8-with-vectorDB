#!/usr/bin/env bash
set -euo pipefail

if ! command -v python3.12 >/dev/null 2>&1; then
  echo "python3.12 not found. Install Python 3.12 before bootstrapping the vector service." >&2
  exit 1
fi

python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip

echo "IMPORTANT: install the appropriate PyTorch wheel for Python 3.12." >&2
echo "Reference: https://pytorch.org/get-started/locally/" >&2
echo "Example (CPU): pip install --index-url https://download.pytorch.org/whl/cpu torch torchvision torchaudio" >&2
read -p "Press Enter after installing the PyTorch wheel..." _

pip install --upgrade -r ../../requirements-vector-service.txt

echo "Environment ready. Copy .env.example to .env and adjust credentials." >&2
