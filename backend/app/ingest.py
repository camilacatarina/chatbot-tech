"""Pipeline de ingestão: idempotente (hash SHA-256), com manifesto e log de eventos."""
import hashlib
import sqlite3
import threading
import time
from contextlib import contextmanager
from pathlib import Path

from .config import settings
from .readers import SUPPORTED, read_file
from .store import get_store

_lock = threading.Lock()  # serializa ingestões (upload e watcher podem coincidir)

SCHEMA = """
CREATE TABLE IF NOT EXISTS files (
    source TEXT PRIMARY KEY, sha256 TEXT, chunks INTEGER, updated_at TEXT);
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, source TEXT,
    status TEXT, chunks INTEGER, detail TEXT, origem TEXT);
"""


@contextmanager
def _db():
    settings.ensure_dirs()
    con = sqlite3.connect(settings.manifest_path)
    con.executescript(SCHEMA)
    try:
        yield con
        con.commit()
    finally:
        con.close()


def _agora() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S")


def log_event(source: str, status: str, chunks: int = 0, detail: str = "", origem: str = "pasta") -> dict:
    with _db() as con:
        cur = con.execute(
            "INSERT INTO events (ts, source, status, chunks, detail, origem) VALUES (?,?,?,?,?,?)",
            (_agora(), source, status, chunks, detail, origem),
        )
        return {
            "id": cur.lastrowid, "ts": _agora(), "source": source, "status": status,
            "chunks": chunks, "detail": detail, "origem": origem,
        }


def recent_events(limit: int = 10) -> list[dict]:
    with _db() as con:
        rows = con.execute(
            "SELECT id, ts, source, status, chunks, detail, origem FROM events ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
    cols = ("id", "ts", "source", "status", "chunks", "detail", "origem")
    return [dict(zip(cols, r)) for r in reversed(rows)]


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for bloco in iter(lambda: f.read(1 << 20), b""):
            h.update(bloco)
    return h.hexdigest()


def ingest_file(path: Path, origem: str = "pasta") -> dict:
    """Lê, divide, gera embeddings e grava. Reprocessa só se o conteúdo mudou."""
    path = Path(path)
    source = path.name
    with _lock:
        row = None
        try:
            digest = _sha256(path)
            if path.suffix.lower() == ".pdf":
                digest = hashlib.sha256(f"{digest}:pdf-ocr-v1".encode()).hexdigest()
            with _db() as con:
                row = con.execute("SELECT sha256 FROM files WHERE source=?", (source,)).fetchone()
            registros = read_file(path)
            if row and row[0] == digest:
                return {"source": source, "status": "skipped", "chunks": 0,
                        "detail": "conteúdo idêntico", "origem": origem}

            store = get_store()
            if row:
                store.delete_source(source)  # versão antiga sai antes da nova entrar
            n = store.add(source, registros, digest)
            with _db() as con:
                con.execute(
                    "INSERT OR REPLACE INTO files VALUES (?,?,?,?)", (source, digest, n, _agora())
                )
            return log_event(source, "updated" if row else "ingested", n, origem=origem)
        except Exception as e:  # o pipeline nunca derruba o servidor
            if (
                path.suffix.lower() == ".pdf"
                and ("OCR indisponível" in str(e) or "Falha no OCR" in str(e))
                and row
            ):
                get_store().delete_source(source)
                with _db() as con:
                    con.execute("DELETE FROM files WHERE source=?", (source,))
            return log_event(source, "failed", 0, str(e), origem)


def remove_source(source: str, origem: str = "pasta") -> dict:
    with _lock:
        get_store().delete_source(source)
        with _db() as con:
            con.execute("DELETE FROM files WHERE source=?", (source,))
        return log_event(source, "removed", 0, origem=origem)


def learn_text(texto: str) -> dict:
    get_store().learn(texto)
    return log_event("conversa", "learned", 1, origem="conversa")


def scan_inbox() -> None:
    """Varredura inicial: ingere o que chegou offline e remove o que foi apagado."""
    settings.ensure_dirs()
    presentes = set()
    for p in sorted(settings.inbox.iterdir()):
        if p.is_file() and p.suffix.lower() in SUPPORTED and not p.name.startswith("."):
            presentes.add(p.name)
            ingest_file(p)
    with _db() as con:
        conhecidos = {r[0] for r in con.execute("SELECT source FROM files")}
    for fonte in conhecidos - presentes:
        remove_source(fonte)
