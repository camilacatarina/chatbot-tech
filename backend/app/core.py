"""Lógica de conversa compartilhada entre a CLI e a API web."""
import re

from .config import settings
from .ingest import learn_text
from .llm import answer, rotulo
from .store import get_store

LEARN_RE = re.compile(r"^(aprenda|lembre|memorize|guarde)(\s+que|:)?\s+(.+)$", re.I | re.S)


def handle_message(message: str, history: list[dict] | None = None) -> dict:
    """Ensina (se a frase começar com 'aprenda que ...') ou responde uma pergunta."""
    message = message.strip()
    m = LEARN_RE.match(message)
    if m:
        learn_text(m.group(3).strip())
        return {"answer": "Anotado.", "sources": [], "learned": True}

    extensions = {".pdf"} if re.search(r"\bpdf\b", message, re.I) else None
    hits = [
        h for h in get_store().search(message, extensions=extensions)
        if h["score"] >= settings.min_score
    ]
    resposta = answer(message, hits, history or [])
    fontes = list(dict.fromkeys(rotulo(h) for h in hits))
    return {"answer": resposta, "sources": fontes, "learned": False}
