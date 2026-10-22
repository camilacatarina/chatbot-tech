from types import SimpleNamespace

import app.llm as llm


def test_provedor_explicitamente_ollama(monkeypatch):
    monkeypatch.setattr(llm, "settings", SimpleNamespace(chat_provider="ollama"))
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    assert llm.provedor_ativo() == "ollama"
    assert llm.llm_rotulo() == "Ollama"


def test_chamada_ollama_envia_historico_e_prompt(monkeypatch):
    settings = SimpleNamespace(ollama_model="llama-teste", ollama_url="http://localhost:11434")
    monkeypatch.setattr(llm, "settings", settings)
    requisicoes = []

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return b'{"message":{"content":"Resposta local"}}'

    def fake_urlopen(request, timeout):
        requisicoes.append((request, timeout))
        return Response()

    monkeypatch.setattr(llm, "urlopen", fake_urlopen)

    resultado = llm._answer_ollama(
        "Instrucoes", [{"role": "user", "content": "Oi"}]
    )

    assert resultado == "Resposta local"
    request, timeout = requisicoes[0]
    assert request.full_url == "http://localhost:11434/api/chat"
    assert timeout == 180


def test_prompt_pede_resposta_em_markdown_organizado(monkeypatch):
    monkeypatch.setattr(llm, "settings", SimpleNamespace(chat_provider="ollama"))
    capturado = {}

    def fake_ollama(system, messages):
        capturado["system"] = system
        capturado["messages"] = messages
        return "**Resposta**"

    monkeypatch.setattr(llm, "_answer_ollama", fake_ollama)

    resposta = llm.answer("Resuma o documento", [], [])

    assert resposta == "**Resposta**"
    assert "resposta direta em uma ou duas frases" in capturado["system"]
    assert "tópicos de nível único" in capturado["system"]
    assert "[arquivo, página]" in capturado["system"]
