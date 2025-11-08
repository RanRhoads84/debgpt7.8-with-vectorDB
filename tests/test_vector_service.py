from debgpt.vector_service import app as app_module
import sys
import types
from pathlib import Path

import numpy as np
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402  pylint: disable=wrong-import-position


class DummyPointStruct:
    def __init__(self, id, vector, payload):
        self.id = id
        self.vector = vector
        self.payload = payload


class DummyFilter:
    def __init__(self, must=None):
        self.must = must or []


class DummyFieldCondition:
    def __init__(self, **kwargs):
        self.kwargs = kwargs


class DummyMatchValue:
    def __init__(self, value):
        self.value = value


class DummyVectorParams:
    def __init__(self, size, distance):
        self.size = size
        self.distance = distance


class FakeQdrantClient:
    def __init__(self):
        self.points = {}
        self.collection_created = False

    class _Collections:
        def __init__(self):
            self.collections = []

    def get_collections(self):  # pragma: no cover - trivial
        return self._Collections()

    def recreate_collection(self, collection_name, vectors_config):  # noqa: D401 pylint: disable=unused-argument
        self.collection_created = True

    def upsert(self, collection_name, points):  # noqa: D401 pylint: disable=unused-argument
        for point in points:
            self.points[point.id] = point

    def search(self, collection_name, query_vector, limit, with_payload, with_vectors, query_filter):  # noqa: D401 pylint: disable=unused-argument
        results = []
        for idx, point in list(self.points.items())[:limit]:
            results.append(types.SimpleNamespace(
                id=idx, score=1.0, payload=point.payload))
        return results

    def delete(self, collection_name, points):  # noqa: D401 pylint: disable=unused-argument
        for point_id in points:
            self.points.pop(point_id, None)


class FakeEmbedder:
    def encode(self, text, convert_to_numpy=True):  # pylint: disable=unused-argument
        vector = np.array([float(len(text))], dtype=np.float32)
        return vector


@pytest.fixture(name="test_app")
def fixture_test_app():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    app_module.Base.metadata.create_all(engine)
    session_factory = sessionmaker(
        bind=engine, autoflush=False, autocommit=False)

    fake_qdrant = FakeQdrantClient()
    fake_embedder = FakeEmbedder()

    # Patch optional classes when qdrant_client is not installed.
    originals = {
        "PointStruct": app_module.PointStruct,
        "Filter": app_module.Filter,
        "FieldCondition": app_module.FieldCondition,
        "MatchValue": app_module.MatchValue,
        "VectorParams": app_module.VectorParams,
    }
    if app_module.PointStruct is None:
        app_module.PointStruct = DummyPointStruct
    if app_module.Filter is None:
        app_module.Filter = DummyFilter
    if app_module.FieldCondition is None:
        app_module.FieldCondition = DummyFieldCondition
    if app_module.MatchValue is None:
        app_module.MatchValue = DummyMatchValue
    if app_module.VectorParams is None:
        app_module.VectorParams = DummyVectorParams

    settings = app_module.Settings(sqlite_path="sqlite:///:memory:")
    test_app = app_module.create_app(
        settings=settings,
        qdrant_client=fake_qdrant,
        embedding_model=fake_embedder,
        session_factory=session_factory,
    )
    yield test_app, fake_qdrant

    # Restore originals to avoid leaking patched placeholders.
    app_module.PointStruct = originals["PointStruct"]
    app_module.Filter = originals["Filter"]
    app_module.FieldCondition = originals["FieldCondition"]
    app_module.MatchValue = originals["MatchValue"]
    app_module.VectorParams = originals["VectorParams"]


def test_health_endpoint(test_app):
    app, _ = test_app
    client = TestClient(app)
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_message_and_context_flow(test_app):
    app, qdrant = test_app
    client = TestClient(app)

    payload = {
        "conversation_id": "conv-1",
        "role": "user",
        "text": "hello world",
        "timestamp": 1700000000,
    }
    response = client.post("/message", json=payload)
    assert response.status_code == 200
    message_id = response.json()["id"]
    assert message_id in qdrant.points

    ctx_response = client.get(
        "/context", params={"query": "hello", "conversation_id": "conv-1", "k": 5})
    assert ctx_response.status_code == 200
    items = ctx_response.json()
    assert items
    assert items[0]["conversation_id"] == "conv-1"
