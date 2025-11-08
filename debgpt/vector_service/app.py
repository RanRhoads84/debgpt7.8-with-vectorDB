"""FastAPI application exposing DebGPT's vector-store microservice."""
from __future__ import annotations

import os
import time
import uuid
from typing import Generator, List, Optional

from fastapi import Depends, FastAPI, HTTPException, Request
from pydantic import BaseModel

try:  # Optional dependency (vector service extra)
    from qdrant_client import QdrantClient
    from qdrant_client.http.models import (
        FieldCondition,
        Filter,
        MatchValue,
        PointStruct,
        VectorParams,
    )
except ImportError:  # pragma: no cover - handled at runtime
    QdrantClient = None  # type: ignore
    FieldCondition = Filter = MatchValue = PointStruct = VectorParams = None  # type: ignore

try:  # Optional dependency (vector service extra)
    from sentence_transformers import SentenceTransformer
except ImportError:  # pragma: no cover - handled at runtime
    SentenceTransformer = None  # type: ignore

from sqlalchemy import Column, Integer, String, Text, create_engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from . import backends

Base = declarative_base()


class Message(Base):
    """Relational record for chronological chat history."""

    __tablename__ = "messages"

    id = Column(String, primary_key=True)
    qdrant_id = Column(String, nullable=True)
    conversation_id = Column(String, index=True)
    role = Column(String)
    text = Column(Text)
    timestamp = Column(Integer, index=True)


class Settings(BaseModel):
    """Runtime configuration sourced from environment variables."""

    qdrant_url: str = os.getenv("QDRANT_URL", "http://127.0.0.1:6333")
    qdrant_collection: str = os.getenv("QDRANT_COLLECTION", "chat_messages")
    embedding_model: str = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
    sqlite_path: str = os.getenv("SQLITE_PATH", "sqlite:///./messages.db")
    default_backend: str = os.getenv(
        "VECTOR_SERVICE_DEFAULT_BACKEND", "ollama")
    embedding_dim: Optional[int] = None


class MessageIn(BaseModel):
    conversation_id: str
    role: str
    text: str
    timestamp: Optional[int] = None


class SaveResponse(BaseModel):
    id: str


class QueryResponseItem(BaseModel):
    id: str
    score: float
    conversation_id: Optional[str] = None
    role: Optional[str] = None
    text: Optional[str] = None
    timestamp: Optional[int] = None


class GenerateRequest(BaseModel):
    conversation_id: str
    prompt: str
    backend: Optional[str] = None
    backend_options: Optional[dict] = None


class GenerateResponse(BaseModel):
    reply: str
    backend: str


def _ensure_optional_dependency(name: str, module) -> None:
    if module is None:
        raise RuntimeError(
            f"Optional dependency '{name}' is required. Install the 'vector-service' extra, "
            "e.g. `pip install debgpt[vector-service]`."
        )


def _create_qdrant_client(settings: Settings) -> QdrantClient:
    _ensure_optional_dependency("qdrant-client", QdrantClient)
    client = QdrantClient(url=settings.qdrant_url)
    return client


def _create_embedding_model(settings: Settings) -> SentenceTransformer:
    _ensure_optional_dependency("sentence-transformers", SentenceTransformer)
    model = SentenceTransformer(settings.embedding_model)
    if settings.embedding_dim is None:
        try:
            settings.embedding_dim = model.get_sentence_embedding_dimension()
        except AttributeError:
            pass
    return model


def _create_session_factory(settings: Settings):
    engine = create_engine(settings.sqlite_path, connect_args={
                           "check_same_thread": False})
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)


def _ensure_collection(client: QdrantClient, settings: Settings, dim: int) -> None:
    try:
        collections = client.get_collections()
        existing = {
            c.name for c in collections.collections} if collections else set()
    except Exception as exc:  # pragma: no cover - network failures
        raise RuntimeError(
            f"Unable to reach Qdrant at {settings.qdrant_url}: {exc}")
    if settings.qdrant_collection not in existing:
        client.recreate_collection(
            collection_name=settings.qdrant_collection,
            vectors_config=VectorParams(size=dim, distance="Cosine"),
        )


def create_app(
    *,
    settings: Optional[Settings] = None,
    qdrant_client: Optional[QdrantClient] = None,
    embedding_model: Optional[SentenceTransformer] = None,
    session_factory: Optional[sessionmaker] = None,
) -> FastAPI:
    """Create and configure the FastAPI application.

    Dependencies can be injected for testing by passing explicit instances.
    """

    settings = settings or Settings()
    app = FastAPI(title="debgpt-vector-service")

    app.state.settings = settings
    app.state.qdrant_client = qdrant_client or _create_qdrant_client(settings)
    app.state.embedding_model = embedding_model or _create_embedding_model(
        settings)
    app.state.embedding_dim = (
        settings.embedding_dim
        or getattr(app.state.embedding_model, "get_sentence_embedding_dimension", lambda: None)()
        or 384
    )
    app.state.session_factory = session_factory or _create_session_factory(
        settings)

    _ensure_collection(app.state.qdrant_client,
                       settings, app.state.embedding_dim)

    def get_db(request: Request) -> Generator[Session, None, None]:
        session = request.app.state.session_factory()
        try:
            yield session
        finally:
            session.close()

    def get_qdrant(request: Request) -> QdrantClient:
        return request.app.state.qdrant_client

    def get_embedder(request: Request):  # SentenceTransformer but keep loose for testing
        return request.app.state.embedding_model

    @app.get("/healthz")
    def healthz() -> dict:
        return {"status": "ok"}

    def _persist_message(
        msg: MessageIn,
        db: Session,
        client: QdrantClient,
        embedder,
    ) -> SaveResponse:
        if msg.role not in ("user", "assistant"):
            raise HTTPException(
                status_code=400, detail="role must be 'user' or 'assistant'")

        timestamp = msg.timestamp or int(time.time())
        message_id = str(uuid.uuid4())

        embedding = embedder.encode(msg.text, convert_to_numpy=True)
        if embedding.ndim != 1:
            raise HTTPException(
                status_code=400, detail="Embedding must be a 1-D vector")

        payload = {
            "conversation_id": msg.conversation_id,
            "role": msg.role,
            "text": msg.text,
            "timestamp": timestamp,
        }
        point = PointStruct(
            id=message_id, vector=embedding.tolist(), payload=payload)
        client.upsert(collection_name=settings.qdrant_collection,
                      points=[point])

        record = Message(
            id=message_id,
            qdrant_id=message_id,
            conversation_id=msg.conversation_id,
            role=msg.role,
            text=msg.text,
            timestamp=timestamp,
        )
        db.add(record)
        db.commit()
        return SaveResponse(id=message_id)

    @app.post("/message", response_model=SaveResponse)
    def save_message(
        msg: MessageIn,
        db: Session = Depends(get_db),
        client: QdrantClient = Depends(get_qdrant),
        embedder=Depends(get_embedder),
    ) -> SaveResponse:
        return _persist_message(msg, db, client, embedder)

    @app.get("/context", response_model=List[QueryResponseItem])
    def get_context(
        query: str,
        conversation_id: Optional[str] = None,
        k: int = 5,
        client: QdrantClient = Depends(get_qdrant),
        embedder=Depends(get_embedder),
    ) -> List[QueryResponseItem]:
        if not query:
            raise HTTPException(status_code=400, detail="query required")
        query_vector = embedder.encode(query, convert_to_numpy=True).tolist()
        q_filter = None
        if conversation_id:
            q_filter = Filter(
                must=[FieldCondition(key="conversation_id",
                                     match=MatchValue(value=conversation_id))]
            )
        results = client.search(
            collection_name=settings.qdrant_collection,
            query_vector=query_vector,
            limit=k,
            with_payload=True,
            with_vectors=False,
            query_filter=q_filter,
        )
        output: List[QueryResponseItem] = []
        for match in results:
            payload = match.payload or {}
            output.append(
                QueryResponseItem(
                    id=str(match.id),
                    score=float(match.score),
                    conversation_id=payload.get("conversation_id"),
                    role=payload.get("role"),
                    text=payload.get("text"),
                    timestamp=payload.get("timestamp"),
                )
            )
        return output

    @app.get("/conversation/{conversation_id}/history", response_model=List[QueryResponseItem])
    def get_history(conversation_id: str, limit: int = 200, db: Session = Depends(get_db)) -> List[QueryResponseItem]:
        rows = (
            db.query(Message)
            .filter(Message.conversation_id == conversation_id)
            .order_by(Message.timestamp.asc())
            .limit(limit)
            .all()
        )
        return [
            QueryResponseItem(
                id=row.id,
                score=0.0,
                conversation_id=row.conversation_id,
                role=row.role,
                text=row.text,
                timestamp=row.timestamp,
            )
            for row in rows
        ]

    @app.delete("/conversation/{conversation_id}")
    def delete_conversation(
        conversation_id: str,
        db: Session = Depends(get_db),
        client: QdrantClient = Depends(get_qdrant),
    ) -> dict:
        ids = [row.id for row in db.query(Message).filter(
            Message.conversation_id == conversation_id).all()]
        if ids:
            client.delete(
                collection_name=settings.qdrant_collection, points=ids)
            db.query(Message).filter(Message.id.in_(ids)
                                     ).delete(synchronize_session=False)
            db.commit()
        return {"deleted_ids": ids}

    @app.get("/export/{conversation_id}")
    def export_conversation(conversation_id: str, db: Session = Depends(get_db)) -> dict:
        rows = (
            db.query(Message)
            .filter(Message.conversation_id == conversation_id)
            .order_by(Message.timestamp.asc())
            .all()
        )
        return {
            "conversation_id": conversation_id,
            "messages": [
                {"id": row.id, "role": row.role,
                    "text": row.text, "timestamp": row.timestamp}
                for row in rows
            ],
        }

    @app.post("/generate", response_model=GenerateResponse)
    def generate(
        request: GenerateRequest,
        db: Session = Depends(get_db),
        client: QdrantClient = Depends(get_qdrant),
        embedder=Depends(get_embedder),
    ) -> GenerateResponse:
        backend_name = request.backend or settings.default_backend
        history_rows = (
            db.query(Message)
            .filter(Message.conversation_id == request.conversation_id)
            .order_by(Message.timestamp.asc())
            .all()
        )
        history_text = "\n".join(
            [f"{row.role}: {row.text}" for row in history_rows[-20:]])
        prompt = f"{history_text}\nuser: {request.prompt}\nassistant:"
        reply = backends.generate_with_backend(
            backend_name, prompt, request.backend_options or {})

        assistant_message = MessageIn(
            conversation_id=request.conversation_id, role="assistant", text=reply)
        _persist_message(assistant_message, db, client, embedder)
        return GenerateResponse(reply=reply, backend=backend_name)

    return app


def build_application() -> FastAPI:
    """Entry-point used by uvicorn."""

    return create_app()


try:
    app = build_application()
except RuntimeError as exc:  # pragma: no cover - fallback when deps missing
    error_detail = str(exc)
    app = FastAPI(title="debgpt-vector-service")

    @app.get("/healthz")
    def missing_dependencies() -> dict:
        raise HTTPException(status_code=503, detail=error_detail)
