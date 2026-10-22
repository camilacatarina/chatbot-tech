"""Transforma arquivos (csv, json, pdf, txt, md) em registros {"text", "meta"}."""
import csv
import io
import json
import re
from pathlib import Path

SUPPORTED = {".csv", ".json", ".pdf", ".txt", ".md"}
TAM = 900            # caracteres por trecho
SOBREPOSICAO = 150   # usada quando um único parágrafo é maior que TAM


def chunk_text(texto: str, tam: int = TAM, sobreposicao: int = SOBREPOSICAO) -> list[str]:
    """Agrupa parágrafos até `tam`; parágrafos gigantes viram janelas com sobreposição."""
    paragrafos = [p.strip() for p in re.split(r"\n\s*\n", texto) if p.strip()]
    trechos: list[str] = []
    atual = ""
    for p in paragrafos:
        if len(p) > tam:
            if atual:
                trechos.append(atual)
                atual = ""
            passo = tam - sobreposicao
            i = 0
            while True:
                trechos.append(p[i : i + tam])
                if i + tam >= len(p):
                    break
                i += passo
        elif not atual:
            atual = p
        elif len(atual) + len(p) + 2 <= tam:
            atual += "\n\n" + p
        else:
            trechos.append(atual)
            atual = p
    if atual:
        trechos.append(atual)
    return trechos


def _ler_texto(path: Path) -> str:
    for enc in ("utf-8-sig", "cp1252"):  # CSVs brasileiros costumam vir em cp1252
        try:
            return path.read_text(encoding=enc)
        except UnicodeDecodeError:
            continue
    return path.read_text(encoding="utf-8", errors="ignore")


def _achatar_json(obj, caminho: str = "") -> list[str]:
    if isinstance(obj, dict):
        linhas = []
        for k, v in obj.items():
            linhas += _achatar_json(v, f"{caminho}.{k}" if caminho else str(k))
        return linhas
    if isinstance(obj, list):
        linhas = []
        for i, v in enumerate(obj):
            linhas += _achatar_json(v, f"{caminho}[{i}]")
        return linhas
    return [f"{caminho}: {obj}"]


def _agrupar(linhas: list[str], tam: int = TAM) -> list[dict]:
    """Junta linhas em trechos de até `tam` caracteres, guardando o intervalo de linhas."""
    registros, bloco, inicio = [], [], 1
    for n, linha in enumerate(linhas, start=1):
        if bloco and sum(len(x) + 1 for x in bloco) + len(linha) > tam:
            registros.append({"text": "\n".join(bloco), "meta": {"linhas": f"{inicio}-{n - 1}"}})
            bloco, inicio = [], n
        bloco.append(linha)
    if bloco:
        registros.append({"text": "\n".join(bloco), "meta": {"linhas": f"{inicio}-{len(linhas)}"}})
    return registros


def _csv(path: Path) -> list[dict]:
    texto = _ler_texto(path)
    cabecalho = texto.splitlines()[0] if texto.strip() else ""
    delim = max(",;\t|", key=cabecalho.count)
    linhas = [
        "; ".join(f"{k}: {v}" for k, v in row.items() if k and v not in (None, ""))
        for row in csv.DictReader(io.StringIO(texto), delimiter=delim)
    ]
    return _agrupar([l for l in linhas if l])


def _json(path: Path) -> list[dict]:
    dados = json.loads(_ler_texto(path))
    if isinstance(dados, list):
        linhas = ["; ".join(_achatar_json(item)) for item in dados]
    else:
        linhas = _achatar_json(dados)
    return _agrupar(linhas)


def _pdf(path: Path) -> list[dict]:
    from pypdf import PdfReader

    registros = []
    paginas = PdfReader(str(path)).pages
    for num, pagina in enumerate(paginas, start=1):
        texto = pagina.extract_text() or ""
        if not texto.strip():
            texto = _ocr_pdf(path, num - 1)
        for trecho in chunk_text(texto):
            registros.append({"text": trecho, "meta": {"pagina": num}})
    return registros


def _ocr_pdf(path: Path, indice_pagina: int) -> str:
    try:
        import pypdfium2 as pdfium
        import pytesseract
    except ImportError as e:
        raise ValueError(
            "OCR indisponível: instale as dependências do backend com "
            "'python -m pip install -r requirements.txt'."
        ) from e

    try:
        documento = pdfium.PdfDocument(str(path))
        pagina = documento[indice_pagina]
        try:
            imagem = pagina.render(scale=2).to_pil()
            return pytesseract.image_to_string(imagem, lang="por+eng").strip()
        finally:
            pagina.close()
            documento.close()
    except pytesseract.TesseractNotFoundError as e:
        raise ValueError(
            "OCR indisponível: instale o Tesseract OCR e confirme que ele está no PATH."
        ) from e
    except pytesseract.TesseractError as e:
        raise ValueError(
            "Falha no OCR. Confira se os dados dos idiomas português (por) e inglês (eng) "
            "estão instalados no Tesseract."
        ) from e


def read_file(path: Path) -> list[dict]:
    ext = path.suffix.lower()
    if ext == ".csv":
        return _csv(path)
    if ext == ".json":
        return _json(path)
    if ext == ".pdf":
        return _pdf(path)
    if ext in {".txt", ".md"}:
        return [{"text": t, "meta": {}} for t in chunk_text(_ler_texto(path))]
    raise ValueError(f"formato '{ext}' não suportado (use {', '.join(sorted(SUPPORTED))})")
