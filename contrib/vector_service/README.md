# DebGPT Vector Service

This helper directory contains deployment assets for the optional FastAPI
vector-store microservice that ships with DebGPT. The service persists chat
history in SQLite while storing semantic embeddings in Qdrant. It also exposes
utility endpoints to retrieve conversation context and trigger language-model
responses via pluggable backends (Ollama, llama.cpp, OpenAI, Google Vertex AI,
Hugging Face Inference).

## Layout

- `docker-compose.yml` – single-node Qdrant instance bound to localhost.
- `.env.example` – environment template for the FastAPI service.
- `bootstrap_env.sh` – convenience script to create a virtual environment and
  install dependencies (prompts for manual PyTorch installation when needed).
- `start_services.sh` – launches Qdrant and runs Uvicorn with auto-reload for
  local development.
- `test_suite.sh` – curl-based smoke test that exercises the health, message,
  and context endpoints.
- `nginx/debgpt-vector.conf` – reverse-proxy example terminating TLS.
- `systemd/debgpt-vector.service` – sample unit file to run the service on boot.

## Quick Start

1. Copy `.env.example` to `.env` and adjust credentials (OpenAI, Hugging Face,
   Vertex AI, etc.).
2. Run `bash bootstrap_env.sh` to create a Python 3.12 virtual environment and
   install dependencies. Follow the prompt to install the appropriate PyTorch
   wheel from https://pytorch.org/get-started/locally/.
3. Launch dependencies for development:

   ```bash
   docker compose up -d
   source .venv/bin/activate
   uvicorn debgpt.vector_service.app:app --host 127.0.0.1 --port 8000 --reload
   ```

4. Execute `./test_suite.sh` to verify basic connectivity.

For production deployment, adapt the provided Nginx configuration and systemd
unit, updating the paths and domain name to match your environment. Ensure that
Qdrant and the FastAPI service remain bound to `127.0.0.1`, exposing only the
reverse proxy to the public internet.
