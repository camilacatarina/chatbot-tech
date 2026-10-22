"""Geração de respostas com Ollama, Gemini, Anthropic ou modo local extrativo."""
import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .config import settings

_client = None
SEM_RESPOSTA = (
    "Não encontrei nada sobre isso no que aprendi. "
    "Envie um arquivo ou escreva “aprenda que …”."
)


def provedor_ativo() -> str:
    provider = settings.chat_provider
    if provider != "auto":
        return provider
    if os.getenv("GEMINI_API_KEY"):
        return "gemini"
    if os.getenv("ANTHROPIC_API_KEY"):
        return "anthropic"
    return "local"


def llm_ativo() -> bool:
    return provedor_ativo() != "local"


def llm_rotulo() -> str:
    return {"anthropic": "Claude", "gemini": "Gemini", "ollama": "Ollama", "local": "local"}.get(
        provedor_ativo(), provedor_ativo()
    )


def _get_client():
    global _client
    if _client is None and provedor_ativo() == "anthropic":
        import anthropic

        _client = anthropic.Anthropic()
    return _client


def rotulo(hit: dict) -> str:
    m = hit["meta"]
    extra = f" p.{m['pagina']}" if "pagina" in m else f" linhas {m['linhas']}" if "linhas" in m else ""
    return f"{m['source']}{extra}"


def answer(pergunta: str, hits: list[dict], historico: list[dict]) -> str:
    provider = provedor_ativo()
    if provider == "local":
        if not hits:
            return SEM_RESPOSTA
        trechos = "\n\n".join(f"[{rotulo(h)}]\n{h['text']}" for h in hits[:3])
        if "resum" in pergunta.casefold():
            return f"No modo local, consigo localizar trechos, mas não gerar um resumo.\n\n{trechos}"
        return trechos

    contexto = "\n\n---\n".join(f"[{rotulo(h)}]\n{h['text']}" for h in hits)
    sistema = (
        "Você é um assistente especializado em tecnologia, incluindo software, hardware, "
        "inteligência artificial, redes e suporte técnico. Responda em português, com clareza "
        "e precisão. Para perguntas sobre os arquivos, use somente o contexto abaixo; se a "
        "informação pedida sobre os arquivos não estiver nele, diga isso sem inventar e cite "
        "a fonte entre colchetes. Perguntas gerais de tecnologia podem ser respondidas com "
        "seu conhecimento, mesmo sem arquivos relevantes. "
        "Quando pedirem um resumo de um documento, sintetize suas ideias principais em vez de "
        "copiar os trechos. Formate sempre em Markdown simples seguindo estas regras: comece "
        "com uma resposta direta em uma ou duas frases; use subtítulos curtos apenas se houver "
        "mais de um assunto; quando uma lista ajudar, use tópicos de nível único, uma ideia por "
        "tópico e frases curtas; destaque em negrito somente termos-chave; não repita a mesma "
        "ideia, não crie introduções genéricas e evite parágrafos longos. Para resumos, organize "
        "em 'Resumo' e, se necessário, 'Pontos principais'. Inclua a fonte no fim da afirmação "
        "ou tópico correspondente, no formato [arquivo, página].\n\n"
        "CONTEXTO DOS ARQUIVOS (pode estar vazio):\n" + contexto
    )
    msgs = [
        {"role": m["role"], "content": m["content"]}
        for m in historico[-6:]
        if m.get("role") in ("user", "assistant") and isinstance(m.get("content"), str)
    ]
    msgs.append({"role": "user", "content": pergunta})
    try:
        if provider == "ollama":
            return _answer_ollama(sistema, msgs)
        if provider == "gemini":
            return _answer_gemini(sistema, msgs)
        if provider == "anthropic":
            client = _get_client()
            r = client.messages.create(
                model=settings.llm_model, max_tokens=1000, system=sistema, messages=msgs
            )
            return "".join(b.text for b in r.content if b.type == "text")
        return f"Provedor de IA inválido: {provider}. Use ollama, gemini, anthropic ou local."
    except Exception:
        trechos = "\n\n".join(h["text"] for h in hits[:3])
        detalhe = {
            "ollama": "Não consegui conectar ao Ollama. Confira se ele está aberto e se o modelo está instalado.",
            "gemini": "Não consegui consultar o Gemini. Confira GEMINI_API_KEY e sua conexão.",
            "anthropic": "Não consegui consultar a Anthropic. Confira ANTHROPIC_API_KEY e sua conexão.",
        }.get(provider, "Falha ao consultar o modelo.")
        return f"{detalhe}\n\nTrechos encontrados:\n\n{trechos}"


def _answer_ollama(system: str, messages: list[dict]) -> str:
    payload = json.dumps(
        {"model": settings.ollama_model, "stream": False,
         "options": {"temperature": 0.2},
         "messages": [{"role": "system", "content": system}, *messages]}
    ).encode("utf-8")
    request = Request(
        f"{settings.ollama_url.rstrip('/')}/api/chat",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(request, timeout=180) as response:
        return json.loads(response.read().decode("utf-8"))["message"]["content"]


def _answer_gemini(system: str, messages: list[dict]) -> str:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY não configurada")
    from google import genai
    from google.genai import types

    contents = "\n\n".join(
        f"{message['role']}: {message['content']}" for message in messages
    )
    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model=settings.gemini_model,
        contents=contents,
        config=types.GenerateContentConfig(system_instruction=system, max_output_tokens=1000),
    )
    return response.text or "Não recebi uma resposta do Gemini."
