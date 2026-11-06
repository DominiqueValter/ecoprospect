import hashlib
import http.client
import json
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from sqlalchemy.orm import Session
from app.database.connection import SessionLocal
from app.models.publicacao import PublicacaoBruta

BASE = "https://www.dioe.pr.gov.br"
URL_DATA = BASE + "/apifront/portal/edicoes/edicoes_from_data/{data}.json"
URL_ULTIMAS = BASE + "/apifront/portal/edicoes/ultimas_edicoes.json"
URL_SUMARIO = BASE + "/portal/visualizacoes/view_html_diario/{ed}"
URL_MATERIA = BASE + "/apifront/portal/edicoes/publicacoes_ver_conteudo/{mat}/{ed}"
URL_VER_HTML = BASE + "/portal/visualizacoes/html/{ed}/#e:{ed}"
URL_PDF = BASE + "/portal/edicoes/download/{ed}"

UA = {"User-Agent": "Mozilla/5.0 (coletor-ecoprospect-dioe)"}


# ------------------------------------------------------------------ HTTP Helpers

def get(url, tentativas=5, pausa=3.0):
    for t in range(tentativas):
        try:
            with urlopen(Request(url, headers=UA), timeout=60) as r:
                bruto = r.read()
            try:
                return bruto.decode("utf-8")
            except UnicodeDecodeError:
                return bruto.decode("latin-1")
        except HTTPError as e:
            if e.code in (400, 404, 410):
                return None
            print(f"  HTTP {e.code}: {url} (tentativa {t + 1})", file=sys.stderr)
        except (URLError, OSError, http.client.HTTPException) as e:
            print(f"  Rede: {url}: {e!r} (tentativa {t + 1})", file=sys.stderr)
        time.sleep(pausa * (t + 1))
    return None


def get_json(url):
    txt = get(url)
    if not txt:
        return None
    try:
        return json.loads(txt)
    except json.JSONDecodeError:
        return None


# ------------------------------------------------------------------ Sumário HTML Parser

class _Sumario(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.pilha, self.itens = [], []
        self._em_pasta, self._link, self._buf = False, None, ""

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "li":
            self.pilha.append(None)
        elif tag == "span" and a.get("class") == "folder":
            self._em_pasta, self._buf = True, ""
        elif tag == "a" and a.get("class") == "linkMateria":
            self._link, self._buf = a, ""

    def handle_endtag(self, tag):
        if tag == "li" and self.pilha:
            self.pilha.pop()
        elif tag == "span" and self._em_pasta:
            self._em_pasta = False
            if self.pilha:
                self.pilha[-1] = " ".join(self._buf.split())
        elif tag == "a" and self._link is not None:
            self.itens.append({
                "caminho": [p for p in self.pilha if p],
                "id_materia": self._link.get("identificador") or self._link.get("data-materia-id"),
                "protocolo": self._link.get("data-protocolo", ""),
                "titulo": " ".join(self._buf.split()),
            })
            self._link = None

    def handle_data(self, data):
        if self._em_pasta or self._link is not None:
            self._buf += data


def ler_sumario(id_edicao):
    html = get(URL_SUMARIO.format(ed=id_edicao))
    if not html:
        return []
    p = _Sumario()
    p.feed(html)
    return p.itens


# ------------------------------------------------------------------ Extrator de Texto

class _Texto(HTMLParser):
    BLOCOS = {"p", "div", "br", "li", "tr", "td", "h1", "h2", "h3", "h4", "h5", "h6", "table"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.partes, self._ign = [], 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "head"):
            self._ign += 1
        elif tag in self.BLOCOS:
            self.partes.append(" ")

    def handle_endtag(self, tag):
        if tag in ("script", "style", "head"):
            self._ign = max(0, self._ign - 1)
        elif tag in self.BLOCOS:
            self.partes.append(" ")

    def handle_data(self, data):
        if not self._ign:
            self.partes.append(data)


def html_para_texto(html):
    p = _Texto()
    p.feed(html)
    return re.sub(r"\s+", " ", "".join(p.partes).replace("\xa0", " ")).strip()


# ------------------------------------------------------------------ Fallback PDF

def sumulas_do_pdf(id_ed):
    import shutil
    import subprocess
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        pdf = Path(tmp) / "ed.pdf"
        try:
            with urlopen(Request(URL_PDF.format(ed=id_ed), headers=UA), timeout=600) as r, open(pdf, "wb") as f:
                shutil.copyfileobj(r, f)
        except (URLError, OSError, http.client.HTTPException) as e:
            print(f"  ! Não foi possível baixar o PDF: {e!r}", file=sys.stderr)
            return {}
        texto = ""
        if shutil.which("pdftotext"):
            subprocess.run(["pdftotext", str(pdf), str(pdf.with_suffix(".txt"))], check=False)
            if pdf.with_suffix(".txt").exists():
                texto = pdf.with_suffix(".txt").read_text(encoding="utf-8", errors="replace")
        if not texto:
            try:
                from pypdf import PdfReader
                texto = "\f".join((p.extract_text() or "") for p in PdfReader(str(pdf)).pages)
            except ImportError:
                print("  ! Instale pypdf para ler o PDF", file=sys.stderr)
                return {}
    texto = re.sub(r"\f\s*\d*\s*\n(?:\s*[^\n]*\|\s*\d{1,2}/\w{3}/\d{4}[^\n]*\n)?", "\n", texto)
    saida = {}
    for m in re.finditer(r"(S[ÚU]MULA\s+DE\s.*?)\n\s*(\d{1,7}/\d{4})\s*(?=\n)", texto, re.S):
        bloco = m.group(1)
        bloco = bloco[bloco.rfind("SÚMULA DE"):] if "SÚMULA DE" in bloco else bloco
        saida[m.group(2)] = " ".join(bloco.split())
    return saida


# ------------------------------------------------------------------ Filtro & Data Normalizer

def selecionar_materias(itens, re_secretaria, re_orgao):
    sel = []
    for it in itens:
        cam = it["caminho"]
        if len(cam) < 2:
            continue
        if not re_secretaria.search(cam[0]) or not re_orgao.search(cam[1]):
            continue
        sel.append(it)
    return sel


def data_iso(d_str):
    try:
        return datetime.strptime(d_str, "%d/%m/%Y").date()
    except (TypeError, ValueError):
        try:
            return datetime.strptime(d_str, "%Y-%m-%d").date()
        except (TypeError, ValueError):
            return date.today()


# ------------------------------------------------------------------ Ingestão para o PostgreSQL

def processar_edicao_db(ed, db: Session, paralelo=4, pausa=0.5):
    id_ed = str(ed["id"])
    itens = ler_sumario(id_ed)
    
    re_sec = re.compile(r"Desenvolvimento Sustent", re.I)
    re_org = re.compile(r"^IAT$|Instituto [ÁA]gua e Terra", re.I)
    
    sel = selecionar_materias(itens, re_sec, re_org)
    print(f"Edição {ed.get('numero')} ({ed.get('data')}, id {id_ed}): {len(itens)} matérias, {len(sel)} selecionadas")

    if not sel:
        return 0

    def baixar_materia(it):
        url = URL_MATERIA.format(mat=it["id_materia"], ed=id_ed)
        h = get(url)
        time.sleep(pausa)
        return it, url, h

    with ThreadPoolExecutor(max_workers=max(1, paralelo)) as ex:
        resultados = list(ex.map(baixar_materia, sel))

    faltando = [it for it, _, h in resultados if h is None]
    do_pdf = {}
    if faltando:
        print(f"  {len(faltando)} matéria(s) sem texto na API; buscando no PDF da edição...")
        do_pdf = sumulas_do_pdf(id_ed)

    novos = 0
    for it, url, html in resultados:
        if html is None:
            texto = do_pdf.get(it["protocolo"])
            if not texto:
                continue
            url = URL_PDF.format(ed=id_ed)
        else:
            texto = html_para_texto(html)

        if not texto:
            continue

        # Calcula o hash do conteúdo para resiliência e deduplicação
        hash_conteudo = hashlib.sha256(f"{id_ed}_{it['id_materia']}_{texto}".encode('utf-8')).hexdigest()

        # Verifica se já existe essa publicação salva no banco
        existente = db.query(PublicacaoBruta).filter(PublicacaoBruta.hash_conteudo == hash_conteudo).first()
        if existente:
            continue

        cam = it["caminho"]
        pub = PublicacaoBruta(
            id_materia=str(it["id_materia"]),
            id_edicao=id_ed,
            numero_edicao=str(ed.get("numero", "")),
            data_edicao=data_iso(ed.get("data")),
            orgao=cam[1] if len(cam) > 1 else "IAT",
            grupo=cam[2] if len(cam) > 2 else "",
            titulo_sumario=it["titulo"],
            texto_integral=texto,
            link_materia=url,
            link_edicao_html=URL_VER_HTML.format(ed=id_ed),
            link_edicao_pdf=URL_PDF.format(ed=id_ed),
            hash_conteudo=hash_conteudo
        )
        db.add(pub)
        novos += 1

    db.commit()
    return novos


def executar_coleta_ultimas_edicoes(qtd_edicoes=3):
    j = get_json(URL_ULTIMAS)
    if not j or j.get("erro"):
        print("Erro ao obter últimas edições do DIOE.")
        return 0

    edicoes = (j.get("itens") or [])[:qtd_edicoes]
    db = SessionLocal()
    total_novos = 0
    try:
        for ed in edicoes:
            total_novos += processar_edicao_db(ed, db)
    finally:
        db.close()
    
    return total_novos


if __name__ == "__main__":
    print("Iniciando teste de coleta e armazenamento no PostgreSQL...")
    novos = executar_coleta_ultimas_edicoes(qtd_edicoes=2)
    print(f"\nColeta concluída! {novos} nova(s) publicação(ões) salva(s) na tabela 'publicacoes_brutas'.")