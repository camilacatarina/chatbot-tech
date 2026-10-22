import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.readers import chunk_text, read_file  # noqa: E402
from app.store import Store  # noqa: E402


def test_chunk_respeita_tamanho():
    texto = "\n\n".join(f"paragrafo {i} " + "x" * 200 for i in range(20))
    assert all(len(c) <= 900 for c in chunk_text(texto))


def test_paragrafo_gigante_vira_janelas_com_sobreposicao():
    trechos = chunk_text("a" * 2000)
    assert len(trechos) == 3
    assert all(len(c) <= 900 for c in trechos)


def test_csv_com_ponto_e_virgula(tmp_path):
    f = tmp_path / "pessoas.csv"
    f.write_text("nome;idade\nAna;30\nBeto;25\n", encoding="utf-8")
    registros = read_file(f)
    assert len(registros) == 1
    assert "nome: Ana" in registros[0]["text"]
    assert "idade: 25" in registros[0]["text"]


def test_json_lista_de_objetos(tmp_path):
    f = tmp_path / "dados.json"
    f.write_text(json.dumps([{"nome": "Ana", "cidade": "Recife"}]), encoding="utf-8")
    texto = read_file(f)[0]["text"]
    assert "nome: Ana" in texto and "cidade: Recife" in texto


def test_formato_invalido(tmp_path):
    f = tmp_path / "x.exe"
    f.write_text("oi")
    try:
        read_file(f)
    except ValueError:
        return
    raise AssertionError("deveria recusar formato não suportado")


def test_pdf_usa_ocr_nas_paginas_sem_texto(tmp_path, monkeypatch):
    import pypdf
    import pypdfium2
    import pytesseract
    from types import SimpleNamespace

    from app.readers import _pdf

    f = tmp_path / "escaneado.pdf"
    paginas = [SimpleNamespace(extract_text=lambda: "")]
    monkeypatch.setattr(pypdf, "PdfReader", lambda _: SimpleNamespace(pages=paginas))
    imagem = object()
    pagina_renderizada = SimpleNamespace(
        render=lambda scale: SimpleNamespace(to_pil=lambda: imagem), close=lambda: None
    )

    class Documento:
        def __getitem__(self, index):
            return pagina_renderizada

        def close(self):
            pass

    monkeypatch.setattr(pypdfium2, "PdfDocument", lambda _: Documento())
    chamadas = []
    monkeypatch.setattr(
        pytesseract,
        "image_to_string",
        lambda img, lang: chamadas.append((img, lang)) or "Texto reconhecido por OCR",
    )

    registros = _pdf(f)

    assert registros == [{"text": "Texto reconhecido por OCR", "meta": {"pagina": 1}}]
    assert chamadas == [(imagem, "por+eng")]


def test_busca_pode_restringir_a_extensao_do_arquivo():
    class Collection:
        def count(self):
            return 3

        def query(self, **kwargs):
            assert kwargs["where"] == {"source": {"$in": ["manual.pdf"]}}
            assert kwargs["n_results"] == 2
            return {"documents": [["trecho do pdf"]], "metadatas": [[{"source": "manual.pdf"}]], "distances": [[0.1]]}

    store = Store.__new__(Store)
    store.col = Collection()
    store.sources = lambda: [
        {"name": "manual.pdf", "chunks": 2},
        {"name": "exemplo.csv", "chunks": 1},
    ]

    resultados = store.search("resuma este pdf", extensions={".pdf"})

    assert len(resultados) == 1
    assert resultados[0]["meta"]["source"] == "manual.pdf"
