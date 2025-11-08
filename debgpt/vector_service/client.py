"""HTTP client helpers for the DebGPT vector microservice."""
from __future__ import annotations

import time
from typing import List, Optional, Sequence

import requests


class VectorServiceClient:
    """Thin wrapper around the vector microservice REST API."""

    def __init__(
        self,
        base_url: str,
        *,
        timeout: float = 5.0,
        enabled: bool = True,
        session: Optional[requests.Session] = None,
        logger: Optional[object] = None,
    ) -> None:
        self.base_url = base_url.rstrip("/") or "http://127.0.0.1:8000"
        self.timeout = timeout
        # Keep vector checks snappy so the CLI does not stall when the service is down.
        self._connect_timeout = max(0.2, min(timeout, 1.0))
        self.enabled = enabled
        self._checked = False
        self._available = False
        self._warned = False
        self._logger = logger
        self._session = session or requests.Session()

    def _url(self, path: str) -> str:
        if not path.startswith("/"):
            path = "/" + path
        return f"{self.base_url}{path}"

    def _log_once(self, message: str) -> None:
        if self._warned or self._logger is None:
            return
        log = getattr(self._logger, "log", None)
        if callable(log):
            log(f"Vector service disabled: {message}")
        self._warned = True

    def _healthcheck(self) -> bool:
        try:
            response = self._session.get(
                self._url("/healthz"),
                timeout=(self._connect_timeout, self.timeout)
            )
            response.raise_for_status()
            return True
        except requests.RequestException as exc:  # pragma: no cover - network
            self._log_once(str(exc))
            return False

    def _ready(self) -> bool:
        if not self.enabled:
            return False
        if not self._checked:
            self._available = self._healthcheck()
            self._checked = True
            if not self._available:
                self.enabled = False
        return self._available

    def query_context(
        self,
        *,
        conversation_id: str,
        query: str,
        top_k: int,
    ) -> List[dict]:
        if not self._ready():
            return []
        try:
            response = self._session.get(
                self._url("/context"),
                params={
                    "conversation_id": conversation_id,
                    "query": query,
                    "k": top_k,
                },
                timeout=(self._connect_timeout, self.timeout),
            )
            response.raise_for_status()
            data = response.json()
        except requests.RequestException as exc:  # pragma: no cover - network
            self._log_once(str(exc))
            self.enabled = False
            return []
        if isinstance(data, Sequence):
            return list(data)
        return []

    def save_message(
        self,
        *,
        conversation_id: str,
        role: str,
        text: str,
        timestamp: Optional[int] = None,
    ) -> Optional[str]:
        if not self._ready():
            return None
        payload = {
            "conversation_id": conversation_id,
            "role": role,
            "text": text,
            "timestamp": timestamp or int(time.time()),
        }
        try:
            response = self._session.post(
                self._url("/message"),
                json=payload,
                timeout=(self._connect_timeout, self.timeout),
            )
            response.raise_for_status()
            data = response.json()
        except requests.RequestException as exc:  # pragma: no cover - network
            self._log_once(str(exc))
            self.enabled = False
            return None
        return data.get("id") if isinstance(data, dict) else None

    def close(self) -> None:
        self._session.close()


__all__ = ["VectorServiceClient"]
