"""CLI entry point for running the vector service with uvicorn."""
from __future__ import annotations

import os
import sys


def main() -> None:
    try:
        import uvicorn
    except ImportError as exc:  # pragma: no cover - runtime guard
        raise SystemExit(
            "uvicorn is required to run the vector service. Install the 'vector-service' extra."
        ) from exc

    host = os.getenv("VECTOR_SERVICE_HOST", "127.0.0.1")
    port = int(os.getenv("VECTOR_SERVICE_PORT", "8000"))
    uvicorn.run("debgpt.vector_service.app:app", host=host, port=port)


if __name__ == "__main__":  # pragma: no cover
    main()
