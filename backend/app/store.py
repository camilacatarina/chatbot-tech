"""Banco vetorial persistente (ChromaDB) com embeddings multilíngues."""
import hashlib
import threading
from collections import Counter
from pathlib import Path

import chromadb
from chromadb.utils import embedding_functions

from .config import settings


class Store:
    def __init__(self):
        settings.ensure_dirs()
        client = chromadb.PersistentClient(path=str(settings.chroma_dir))
        ef = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name=settings.embedding_model
        )
        self.col = client.get_or_create_collection(
            "conhecimento", embedding_function=ef, metadata={"hnsw:space": "cosine"}
        )

    def add(self, source: str, registros: list[dict], digest: str) -> int:
        if not registros:
            raise ValueError("nenhum texto extraído do arquivo (PDF escaneado?)")
        for ini in range(0, len(registros), 64):
            lote = registros[ini : ini + 64]
            self.col.upsert(
                ids=[f"{digest[:12]}-{ini + i}" for i in range(len(lote))],
                documents=[r["text"] for r in lote],
                metadatas=[{"source": source, **r["meta"]} for r in lote],
            )
        return len(registros)

    def learn(self, texto: str) -> None:
        digest = hashlib.sha1(texto.encode()).hexdigest()
        self.col.upsert(
            ids=[f"learn-{digest}"], documents=[texto], metadatas=[{"source": "conversa"}]
        )

    def delete_source(self, source: str) -> None:
        self.col.delete(where={"source": source})

    def search(
        self, pergunta: str, k: int | None = None, extensions: set[str] | None = None
    ) -> list[dict]:
        total = self.col.count()
        if total == 0:
            return []
        where = None
        if extensions:
            sources = [
                source["name"]
                for source in self.sources()
                if Path(source["name"]).suffix.lower() in extensions
            ]
            if not sources:
                return []
            where = {"source": {"$in": sources}}
            total = sum(source["chunks"] for source in self.sources() if source["name"] in sources)
        r = self.col.query(
            query_texts=[pergunta], n_results=min(k or settings.top_k, total), where=where
        )
        return [
            {"text": d, "meta": m, "score": round(1 - dist, 3)}
            for d, m, dist in zip(r["documents"][0], r["metadatas"][0], r["distances"][0])
        ]

    def count(self) -> int:
        return self.col.count()

    def sources(self) -> list[dict]:
        metas = self.col.get(include=["metadatas"])["metadatas"]
        contagem = Counter(m["source"] for m in metas)
        return [{"name": n, "chunks": c} for n, c in sorted(contagem.items())]


_store: Store | None = None
_lock = threading.Lock()


def get_store() -> Store:
    global _store
    with _lock:
        if _store is None:
            _store = Store()
        return _store


def store_pronto() -> bool:
    return _store is not None
