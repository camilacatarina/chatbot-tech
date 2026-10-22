from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .config import ROOT, settings
from .core import handle_message
from .ingest import ingest_file, recent_events
from .llm import llm_ativo, llm_rotulo
from .readers import SUPPORTED
from .store import get_store, store_pronto
from .watcher import start_watcher


@asynccontextmanager
async def lifespan(app: FastAPI):
    observer = start_watcher()
    yield
    observer.stop()
    observer.join()


app = FastAPI(title="Assistente de Tecnologia", lifespan=lifespan)


class ChatIn(BaseModel):
    message: str
    history: list[dict] = []


@app.post("/api/chat")
def chat(body: ChatIn):
    if not body.message.strip():
        raise HTTPException(400, "mensagem vazia")
    return handle_message(body.message, body.history)


@app.post("/api/upload")
def upload(file: UploadFile = File(...)):
    nome = Path(file.filename or "").name
    if Path(nome).suffix.lower() not in SUPPORTED:
        raise HTTPException(400, f"formato não suportado. Use: {', '.join(sorted(SUPPORTED))}")
    settings.ensure_dirs()
    destino = settings.inbox / nome
    destino.write_bytes(file.file.read())  # a pasta é a fonte da verdade
    return ingest_file(destino, origem="upload")


@app.get("/api/stats")
def stats():
    base = {
        "inbox": str(settings.inbox),
        "llm": llm_ativo(),
        "llm_provider": llm_rotulo(),
        "events": recent_events(),
    }
    if not store_pronto():
        return {**base, "ready": False}
    store = get_store()
    return {**base, "ready": True, "chunks": store.count(), "sources": store.sources()}


# Em produção, serve o frontend compilado (npm run build) na mesma porta.
_dist = ROOT / "frontend" / "dist"
if _dist.exists():
    app.mount("/", StaticFiles(directory=_dist, html=True), name="frontend")
