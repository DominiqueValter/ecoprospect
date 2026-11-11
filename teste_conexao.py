import time
import random
import urllib.request
import urllib.parse
from html.parser import HTMLParser


class LeitorResultados(HTMLParser):
    """Extrai título, URL e resumo dos resultados do DuckDuckGo HTML."""

    def __init__(self):
        super().__init__()
        self.resultados = []
        self._resultado_atual = None
        self._capturando_titulo = False
        self._capturando_resumo = False

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        classes = attrs.get("class", "").split()

        # Link principal do resultado
        if tag == "a" and "result__a" in classes:
            self._resultado_atual = {
                "titulo": "",
                "url": attrs.get("href", ""),
                "resumo": "",
            }
            self._capturando_titulo = True

        # Resumo do resultado
        elif "result__snippet" in classes and self._resultado_atual:
            self._capturando_resumo = True

    def handle_data(self, data):
        texto = data.strip()
        if not texto:
            return

        if self._capturando_titulo and self._resultado_atual:
            self._resultado_atual["titulo"] += texto + " "

        elif self._capturando_resumo and self._resultado_atual:
            self._resultado_atual["resumo"] += texto + " "

    def handle_endtag(self, tag):
        if tag == "a" and self._capturando_titulo:
            self._capturando_titulo = False

            if self._resultado_atual:
                self.resultados.append(self._resultado_atual)
                self._resultado_atual = None

        # O resumo pode estar dentro de uma div ou span
        if self._capturando_resumo and tag in ("div", "span"):
            self._capturando_resumo = False


def pesquisar_duckduckgo(consulta, quantidade=8):
    url = "https://html.duckduckgo.com/html/?" + urllib.parse.urlencode({
        "q": consulta
    })

    requisicao = urllib.request.Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
        },
    )

    with urllib.request.urlopen(requisicao, timeout=25) as resposta:
        html = resposta.read().decode("utf-8", errors="replace")

    parser = LeitorResultados()
    parser.feed(html)

    return parser.resultados[:quantidade]


def pesquisar_empresa(nome, cidade=None):
    consultas = [
        f'"{nome}" CNPJ',
        f'"{nome}" telefone email',
        f'"{nome}" empresa endereço',
        f'"{nome}" site:gov.br',
    ]

    if cidade:
        consultas.extend([
            f'"{nome}" "{cidade}" CNPJ',
            f'"{nome}" "{cidade}" licença ambiental',
        ])

    encontrados = {}
    for consulta in consultas:
        print(f"\nPesquisando: {consulta}")

        try:
            resultados = pesquisar_duckduckgo(consulta)

            for item in resultados:
                link = item["url"].strip()
                if link and link not in encontrados:
                    encontrados[link] = item

            # Pausa para reduzir a chance de bloqueio
            time.sleep(random.uniform(2.0, 4.0))

        except Exception as erro:
            print(f"  Não foi possível concluir essa busca: {erro}")

    if not encontrados:
        print("\nNenhum resultado coletado. O mecanismo pode ter bloqueado a consulta.")
        return

    print(f"\nResultados encontrados: {len(encontrados)}")
    for numero, item in enumerate(encontrados.values(), start=1):
        print(f"\n[{numero}] {item['titulo'].strip()}")
        print(f"Link: {item['url']}")
        resumo = item["resumo"].strip()
        if resumo:
            print(f"Resumo: {resumo}")


if __name__ == "__main__":
    nome_empresa = "ZELLAMÓVEIS - COMPRA E VENDA DE IMÓVEIS LTDA"
    cidade = "Paranaguá PR"  # Informe a região conhecida ou use None

    pesquisar_empresa(nome_empresa, cidade)
