import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import "./styles.css";

async function api(path, options) {
  const resp = await fetch(`/api${path}`, options);
  if (!resp.ok) {
    const corpo = await resp.json().catch(() => ({}));
    throw new Error(corpo.detail || resp.statusText);
  }
  return resp.json();
}

const BOAS_VINDAS =
  "Assistente de tecnologia pronto. Pergunte sobre seus documentos ou envie um arquivo.";

export default function App() {
  const [linhas, setLinhas] = useState([{ tipo: "sys", texto: BOAS_VINDAS }]);
  const [entrada, setEntrada] = useState("");
  const [ocupado, setOcupado] = useState(false);
  const [arrastando, setArrastando] = useState(false);
  const [stats, setStats] = useState(null);
  const fim = useRef(null);
  const campo = useRef(null);
  const seletor = useRef(null);
  const historico = useRef([]);
  const ultimoEvento = useRef(null); // null = ainda não fez a primeira leitura

  const add = (linha) => setLinhas((atual) => [...atual, linha]);

  // Status + eventos do pipeline (arquivos que chegaram na pasta monitorada)
  useEffect(() => {
    let vivo = true;
    async function atualizar() {
      try {
        const s = await api("/stats");
        if (!vivo) return;
        setStats(s);
        const maior = s.events.reduce((m, e) => Math.max(m, e.id), 0);
        if (ultimoEvento.current === null) {
          ultimoEvento.current = maior; // não reimprime o histórico antigo
        } else {
          s.events
            .filter((e) => e.id > ultimoEvento.current && e.origem === "pasta")
            .forEach((e) => add({ tipo: e.status === "failed" ? "erro" : "sys", texto: descrever(e) }));
          ultimoEvento.current = Math.max(ultimoEvento.current, maior);
        }
      } catch {
        /* backend fora do ar: tenta de novo no próximo ciclo */
      }
    }
    atualizar();
    const t = setInterval(atualizar, 4000);
    return () => {
      vivo = false;
      clearInterval(t);
    };
  }, []);

  useEffect(() => {
    fim.current?.scrollIntoView({ behavior: "smooth" });
  }, [linhas, ocupado]);

  async function enviar(e) {
    e.preventDefault();
    const texto = entrada.trim();
    if (!texto || ocupado) return;
    setEntrada("");
    add({ tipo: "user", texto });
    setOcupado(true);
    try {
      const r = await api("/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: texto, history: historico.current.slice(-8) }),
      });
      add({ tipo: "bot", texto: r.answer, fontes: r.sources });
      historico.current.push({ role: "user", content: texto }, { role: "assistant", content: r.answer });
    } catch (err) {
      add({ tipo: "erro", texto: err.message });
    } finally {
      setOcupado(false);
      campo.current?.focus();
    }
  }

  async function enviarArquivos(arquivos) {
    for (const f of arquivos) {
      const fd = new FormData();
      fd.append("file", f);
      try {
        const r = await api("/upload", { method: "POST", body: fd });
        add({ tipo: r.status === "failed" ? "erro" : "sys", texto: descrever(r) });
      } catch (err) {
        add({ tipo: "erro", texto: `${f.name}: ${err.message}` });
      }
    }
  }

  function soltar(e) {
    e.preventDefault();
    setArrastando(false);
    enviarArquivos([...e.dataTransfer.files]);
  }

  const status = !stats
    ? "conectando…"
    : !stats.ready
    ? "carregando modelo de embeddings…"
    : `${stats.chunks} trechos · ${stats.sources.length} fontes · modo ${stats.llm_provider} · pasta monitorada: ${stats.inbox}`;

  return (
    <div
      className={`tela ${arrastando ? "arrastando" : ""}`}
      onClick={() => campo.current?.focus()}
      onDragOver={(e) => {
        e.preventDefault();
        setArrastando(true);
      }}
      onDragLeave={() => setArrastando(false)}
      onDrop={soltar}
    >
      <div className="status">{status}</div>

      <div className="log">
        {linhas.map((l, i) => (
          <div key={i} className={`linha ${l.tipo}`}>
            {l.tipo === "bot" ? <ReactMarkdown>{l.texto}</ReactMarkdown> : l.texto}
            {l.fontes?.length > 0 && <span className="fontes">fontes: {l.fontes.join(" · ")}</span>}
          </div>
        ))}
        {ocupado && <div className="linha sys">pensando…</div>}
        <div ref={fim} />
      </div>

      <form className="entrada" onSubmit={enviar}>
        <span className="prompt">você ❯</span>
        <input
          ref={campo}
          type="text"
          value={entrada}
          onChange={(e) => setEntrada(e.target.value)}
          autoFocus
          autoComplete="off"
          spellCheck={false}
          disabled={ocupado}
        />
        <button type="button" className="anexar" title="anexar arquivo" onClick={() => seletor.current?.click()}>
          +
        </button>
        <input
          ref={seletor}
          type="file"
          hidden
          multiple
          accept=".json,.csv,.pdf,.txt,.md"
          onChange={(e) => {
            enviarArquivos([...e.target.files]);
            e.target.value = "";
          }}
        />
      </form>
    </div>
  );
}

function descrever(e) {
  switch (e.status) {
    case "ingested":
      return `Li ${e.source}: ${e.chunks} trechos aprendidos.`;
    case "updated":
      return `${e.source} mudou: memória atualizada (${e.chunks} trechos).`;
    case "removed":
      return `${e.source} saiu da pasta: removido da memória.`;
    case "skipped":
      return `${e.source}: já conhecido, nada mudou.`;
    case "failed":
      return `Falha ao ler ${e.source}: ${e.detail}`;
    default:
      return `${e.source}: ${e.status}`;
  }
}
