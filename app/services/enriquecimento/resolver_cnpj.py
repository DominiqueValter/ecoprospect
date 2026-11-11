# scripts/buscar_empresas.py

import json
import random
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from html.parser import HTMLParser

from app.database.connection import SessionLocal
from app.models.empresa import Empresa  # ajuste para o caminho real do seu modelo


class DuckDuckGoParser(HTMLParser):
    """Extrai título, link e resumo da página HTML de resultados."""

    def __init__(self):
        super().__init__()
        self.items = []
        self.current = None
        self.in_title = False
        self.in_snippet = False

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        classes = attrs.get("class", "").split()

        if tag == "a" and "result__a" in classes:
            self.current = {
                "titulo": "",
                "url": attrs.get("href", ""),
                "resumo": "",
            }
            self.in_title = True

        elif self.current and "result__snippet" in classes:
            self.in_snippet = True

    def handle_data(self, data):
        if not self.current:
            return

        text = data.strip()
        if not text:
            return

        if self.in_title:
            self.current["titulo"] += text + " "
        elif self.in_snippet:
            self.current["resumo"] += text + " "

    def handle_endtag(self, tag):
        if tag == "a" and self.in_title:
            self.in_title = False
            if self.current:
                self.items.append(self.current)
                self.current = None

        if tag in ("div", "span") and self.in_snippet:
            self.in_snippet = False


def pesquisar(consulta, limite=6):
    url = "https://html.duckduckgo.com/html/?" + urllib.parse.urlencode(
        {"q": consulta}
    )
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "pt-BR,pt;q=0.9",
        },
    )

    with urllib.request.urlopen(request, timeout=25) as response:
        html = response.read().decode("utf-8", errors="replace")

    parser = DuckDuckGoParser()
    parser.feed(html)
    return parser.items[:limite]


def montar_consultas(empresa):
    nome = empresa.razao_social.strip()
    local = f"{empresa.municipio} {empresa.uf}".strip()

    return [
        f'"{nome}" "{local}" CNPJ',
        f'"{nome}" "{local}" telefone email',
        f'"{nome}" "{local}" endereço',
        f'"{nome}" "{local}" site:gov.br',
    ]


def main():
    db = SessionLocal()

    try:
        empresas = (
            db.query(Empresa)
            .filter(
                Empresa.tipo_titular == "PJ",
                Empresa.elegivel_prospeccao == "ELEGIVEL",
            )
            .order_by(Empresa.id)
            .all()
        )

        print(f"Empresas selecionadas: {len(empresas)}")

        with open("resultados_busca.jsonl", "a", encoding="utf-8") as arquivo:
            for numero, empresa in enumerate(empresas, start=1):
                print(
                    f"[{numero}/{len(empresas)}] "
                    f"{empresa.razao_social} — {empresa.municipio}/{empresa.uf}"
                )

                resultados_por_url = {}

                for consulta in montar_consultas(empresa):
                    try:
                        for resultado in pesquisar(consulta):
                            link = resultado.get("url", "").strip()
                            if link:
                                resultados_por_url[link] = resultado
                    except Exception as erro:
                        print(f"  Falha na consulta {consulta!r}: {erro}")

                    # Não faça consultas em sequência rápida.
                    time.sleep(random.uniform(2.5, 4.5))

                registro = {
                    "empresa_id": empresa.id,
                    "razao_social": empresa.razao_social,
                    "municipio": empresa.municipio,
                    "uf": empresa.uf,
                    "pesquisado_em": datetime.now(timezone.utc).isoformat(),
                    "resultados": list(resultados_por_url.values()),
                }

                arquivo.write(json.dumps(registro, ensure_ascii=False) + "\n")
                arquivo.flush()
                print(f"  Links coletados: {len(resultados_por_url)}")

    finally:
        db.close()


if __name__ == "__main__":
    main()
