#!/usr/bin/env bash
set -euo pipefail

docker compose up -d
source .venv/bin/activate
uvicorn debgpt.vector_service.app:app --host 127.0.0.1 --port 8000 --reload
