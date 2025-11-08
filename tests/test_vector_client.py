"""Unit tests for the vector service HTTP client."""
from __future__ import annotations

from unittest.mock import MagicMock

import requests

from debgpt.vector_service.client import VectorServiceClient


def test_vector_client_disabled_short_circuits():
    client = VectorServiceClient('http://localhost:8000', enabled=False)
    assert client.query_context(
        conversation_id='conv', query='hello', top_k=3) == []
    assert client.save_message(
        conversation_id='conv', role='user', text='hello') is None


def test_vector_client_failure_disables(monkeypatch):
    session = MagicMock()
    session.get.side_effect = requests.RequestException('boom')
    session.post.side_effect = requests.RequestException('boom')
    client = VectorServiceClient('http://localhost:8000', session=session)
    # First call should trigger health check failure and disable the client
    assert client.query_context(
        conversation_id='conv', query='hello', top_k=3) == []
    assert client.enabled is False
    # Subsequent save_message should no-op because client is disabled
    assert client.save_message(
        conversation_id='conv', role='user', text='hello') is None
