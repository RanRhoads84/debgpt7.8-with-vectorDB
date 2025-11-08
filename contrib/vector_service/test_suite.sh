#!/usr/bin/env bash
set -euo pipefail

BASE_URL=${BASE_URL:-http://127.0.0.1:8000}

command -v jq >/dev/null 2>&1 || {
  echo "jq is required for the test suite." >&2
  exit 1
}

echo "Checking health endpoint..."
curl -sS "$BASE_URL/healthz" | jq

echo "Posting sample message..."
MSG_PAYLOAD='{"conversation_id":"testconv","role":"user","text":"Hello testing","timestamp":1700000000}'
RESP=$(curl -sS -X POST "$BASE_URL/message" -H "Content-Type: application/json" -d "$MSG_PAYLOAD")
echo "Response: $RESP"

echo "Querying semantic context..."
curl -sS "$BASE_URL/context?query=hello&conversation_id=testconv&k=3" | jq
