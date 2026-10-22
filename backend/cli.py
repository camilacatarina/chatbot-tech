#!/usr/bin/env python3
"""Versão terminal (a original do pedido): mesmo núcleo da API, visual de prompt.

Uso (dentro de backend/):  python cli.py
Cole o caminho de um arquivo para ele aprender; "aprenda que ..." ensina; "sair" encerra.
"""
import shutil
import sys
from pathlib import Path

from prompt_toolkit import PromptSession
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.history import FileHistory
from rich.console import Console
from rich.markdown import Markdown

from app.config import settings
from app.core import handle_message
from app.ingest import ingest_file
from app.llm import llm_rotulo
from app.readers import SUPPORTED
from app.store import get_store

console = Console()


def como_arquivo(entrada: str) -> Path | None:
    limpo = entrada.strip().strip("'\"").replace("\\ ", " ")
    try:
        p = Path(limpo).expanduser()
        return p if p.is_file() and p.suffix.lower() in SUPPORTED else None
    except OSError:
        return None


def main():
    settings.ensure_dirs()
    with console.status("[dim]carregando modelo de embeddings…[/dim]"):
        store = get_store()
    modelos = {
        "Ollama": settings.ollama_model,
        "Gemini": settings.gemini_model,
        "Claude": settings.llm_model,
    }
    provedor = llm_rotulo()
    modo = f"{provedor} ({modelos[provedor]})" if provedor in modelos else provedor
    console.print(f"[dim]chatbot · modo {modo} · {store.count()} trechos na memória[/dim]\n")

    sessao = PromptSession(history=FileHistory(str(settings.data_dir / ".historico_cli")))
    historico: list[dict] = []
    while True:
        try:
            entrada = sessao.prompt(
                HTML("<ansigreen><b>você</b></ansigreen> <ansibrightblack>❯</ansibrightblack> ")
            ).strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not entrada:
            continue
        if entrada.lower() in {"sair", "exit", "quit"}:
            break

        arquivo = como_arquivo(entrada)
        if arquivo:
            destino = settings.inbox / arquivo.name
            if arquivo.resolve() != destino.resolve():
                shutil.copy2(arquivo, destino)  # a pasta inbox continua sendo a fonte da verdade
            r = ingest_file(destino, origem="cli")
            msg = {
                "skipped": "já conhecia esse arquivo, nada mudou.",
                "failed": f"[red]erro:[/red] {r['detail']}",
            }.get(r["status"], f"li [b]{arquivo.name}[/b] e aprendi {r['chunks']} trechos.")
            console.print(f"[bold cyan]bot[/bold cyan] [dim]❯[/dim] {msg}\n")
            continue

        with console.status("[dim]pensando…[/dim]", spinner="dots"):
            r = handle_message(entrada, historico)
        historico += [{"role": "user", "content": entrada}, {"role": "assistant", "content": r["answer"]}]
        console.print("[bold cyan]bot[/bold cyan] [dim]❯[/dim]", end=" ")
        console.print(Markdown(r["answer"]))
        if r["sources"]:
            console.print("[dim]fontes: " + " · ".join(r["sources"]) + "[/dim]")
        console.print()


if __name__ == "__main__":
    sys.exit(main())
