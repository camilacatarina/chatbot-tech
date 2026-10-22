# Assistente de Tecnologia com RAG

Chatbot full stack que responde perguntas de tecnologia e consulta arquivos enviados (`.json`, `.csv`, `.pdf`, `.txt`, `.md`).
Usa busca semântica com ChromaDB e pode gerar respostas com Ollama local, Gemini ou Anthropic. Também aceita notas na conversa
com `aprenda que ...`.

```
 data/inbox/  ──watchdog──►  ingestão idempotente  ──►  ChromaDB (embeddings)
 (arquivos)                  hash SHA-256 + manifesto          ▲
                             SQLite + log de eventos           │ busca semântica
 React (prompt) ◄──► FastAPI ◄──► core.handle_message ─────────┘
 CLI (prompt)   ◄───────────────────┘          └──► Ollama, Gemini, Claude ou modo local
```

## Como rodar

### Backend (Windows / PowerShell)

```powershell
cd backend
py -m venv .venv
.venv\Scripts\Activate.ps1
py -m pip install -r requirements.txt
Copy-Item .env.example .env
py -m uvicorn app.main:app --reload --port 8000
```

O arquivo `.env` já seleciona `qwen3:4b`, compatível com a configuração local atual. Mantenha o Ollama aberto e confirme
que o modelo está instalado com `ollama list`; se necessário, execute `ollama pull qwen3:4b`.

Para Gemini, mude `CHAT_PROVIDER` para `gemini` e preencha `GEMINI_API_KEY` no `backend/.env`. O arquivo `.env` é ignorado
pelo Git: não compartilhe nem faça commit dele. Reinicie o backend após mudar a configuração.

### OCR para PDFs escaneados

Instale o Tesseract OCR para Windows e os dados de idioma português (`por`) e inglês (`eng`), depois abra um terminal novo
para atualizar o `PATH`. O backend usa OCR localmente nas páginas sem texto selecionável. As dependências Python de OCR são
instaladas pelo `requirements.txt`.

### Frontend (outro terminal PowerShell)

```powershell
cd frontend
npm install
npm run dev
```

Abra o endereço indicado pelo Vite, normalmente `http://localhost:5173`.

### CLI e testes

Com o ambiente virtual ativo e dentro de `backend`:

```powershell
py cli.py
py -m pytest
```

Na primeira execução, o modelo de embeddings multilíngue (cerca de 470 MB) é baixado. O status no topo da interface mostra
o provedor ativo. Para servir a interface e API pela porta 8000, rode `npm run build` no frontend e depois inicie o backend.

## Decisões de projeto

- **Busca semântica**: `paraphrase-multilingual-MiniLM-L12-v2` (bom em português) + ChromaDB com distância de cosseno.
  Troque o modelo com `EMBEDDING_MODEL`.
- **Pipeline idempotente**: cada arquivo tem SHA-256 no manifesto. Mesmo conteúdo é ignorado; conteúdo alterado
  substitui os trechos antigos; arquivo apagado da pasta sai da memória. Falhas viram evento `failed`, sem derrubar o servidor.
- **Pasta como fonte da verdade**: uploads pela web e pela CLI são gravados em `data/inbox/`, então tudo passa pelo mesmo caminho.
- **Chunking**: parágrafos agrupados em ~900 caracteres; PDFs guardam o número da página; CSV/JSON guardam o intervalo de linhas
  (as respostas citam a fonte).
- **Provedores de resposta**: Ollama local, Gemini, Anthropic ou modo local extrativo. Configure `CHAT_PROVIDER` no `.env`;
  `auto` detecta as chaves Gemini/Anthropic, mas não escolhe Ollama automaticamente.
- **Formatação**: as respostas são renderizadas como Markdown, com instruções para respostas concisas, listas simples e fontes.

## Configuração (variáveis de ambiente)

| Variável | Padrão | Para quê |
|---|---|---|
| `ANTHROPIC_API_KEY` | — | ativa respostas geradas pelo Claude |
| `CHATBOT_MODELO` | `claude-sonnet-5-5` | modelo usado |
| `CHAT_PROVIDER` | `auto` | `ollama`, `gemini`, `anthropic`, `local` ou `auto` |
| `OLLAMA_MODEL` | `qwen3:4b` | modelo instalado no Ollama |
| `OLLAMA_URL` | `http://localhost:11434` | endereço local do Ollama |
| `GEMINI_API_KEY` | — | chave da API Gemini |
| `GEMINI_MODEL` | `gemini-2.5-flash` | modelo Gemini usado |
| `EMBEDDING_MODEL` | `paraphrase-multilingual-MiniLM-L12-v2` | embeddings |
| `TOP_K` / `MIN_SCORE` | `5` / `0.2` | trechos recuperados / similaridade mínima |
| `DATA_DIR` | `./data` | onde ficam inbox, banco vetorial e manifesto |

## Publicar no GitHub

1. Revise `git status` e confirme que `backend/.env`, PDFs, CSVs, banco vetorial e arquivos pessoais não serão enviados.
  O `.gitignore` exclui segredos, dados da inbox e dados locais do ChromaDB.
2. Crie um repositório vazio no GitHub, sem gerar README ou `.gitignore` nele.
3. Na pasta raiz do projeto, inicialize e envie o código:

```powershell
git init
git add .
git status
git commit -m "Versão inicial do assistente de tecnologia"
git branch -M main
git remote add origin https://github.com/SEU-USUARIO/SEU-REPOSITORIO.git
git push -u origin main
```

Substitua a URL pelo endereço do seu repositório e confira a lista do `git status` antes do commit.
