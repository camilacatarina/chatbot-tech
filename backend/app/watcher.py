"""Monitora data/inbox e mantém a memória sincronizada com a pasta."""
import threading
import time
from pathlib import Path

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from .config import settings
from .ingest import SUPPORTED, ingest_file, remove_source, scan_inbox
from .store import get_store


def _esperar_estabilizar(path: Path, tentativas: int = 20) -> bool:
    """Espera o arquivo parar de crescer (cópias grandes disparam vários eventos)."""
    anterior = -1
    for _ in range(tentativas):
        try:
            atual = path.stat().st_size
        except FileNotFoundError:
            return False
        if atual == anterior and atual > 0:
            return True
        anterior = atual
        time.sleep(0.5)
    return False


def _relevante(path: Path) -> bool:
    return path.suffix.lower() in SUPPORTED and not path.name.startswith(".")


class _Handler(FileSystemEventHandler):
    def _processar(self, path: Path):
        if _esperar_estabilizar(path):
            ingest_file(path)  # hash igual => ignorado, então eventos duplicados são inofensivos

    def _disparar(self, event):
        path = Path(event.src_path)
        if not event.is_directory and _relevante(path):
            threading.Thread(target=self._processar, args=(path,), daemon=True).start()

    def on_created(self, event):
        self._disparar(event)

    def on_modified(self, event):
        self._disparar(event)

    def on_deleted(self, event):
        path = Path(event.src_path)
        if not event.is_directory and _relevante(path):
            remove_source(path.name)


def _varredura_inicial():
    get_store()  # carrega o modelo de embeddings antes das primeiras requisições
    scan_inbox()


def start_watcher() -> Observer:
    settings.ensure_dirs()
    observer = Observer()
    observer.schedule(_Handler(), str(settings.inbox), recursive=False)
    observer.start()
    threading.Thread(target=_varredura_inicial, daemon=True).start()
    return observer
