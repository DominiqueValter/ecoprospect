"""
Carrega os Dados Abertos do CNPJ (Receita Federal) na tabela cnpj_base, filtrando por UF.

Por que: nenhuma API pública gratuita busca CNPJ pela razão social, e raspar
Google/Bing/DuckDuckGo esbarra em anti-robô. A base aberta resolve isso localmente.

Download (mensal): https://arquivos.receitafederal.gov.br/dados/cnpj/dados_abertos_cnpj/
Baixe para uma pasta, sem descompactar:
  Empresas0.zip ... Empresas9.zip
  Estabelecimentos0.zip ... Estabelecimentos9.zip
  Municipios.zip

Uso:
  python -m app.services.enriquecimento.importar_base_cnpj --pasta data/cnpj --uf PR
  python -m app.services.enriquecimento.importar_base_cnpj --pasta data/cnpj --uf PR SC --incluir-inativas

A carga substitui as linhas das UFs informadas. Para o PR (estabelecimentos ativos)
leva alguns minutos e usa algumas centenas de MB de memória.
"""
import argparse
import csv
import glob
import io
import os
import sys
import tempfile
import zipfile
from datetime import datetime

from sqlalchemy import delete, insert

from app.database.connection import engine, Base
from app.models.cnpj_base import CnpjBase
from app.services.enriquecimento.normalizacao import normalizar, raiz

csv.field_size_limit(10 ** 7)

COLUNAS = [
    "cnpj", "cnpj_basico", "matriz", "razao_social", "razao_normalizada", "razao_raiz",
    "nome_fantasia", "fantasia_normalizada", "situacao_cadastral", "uf", "municipio",
    "municipio_normalizado", "cnae_principal", "ddd_telefone_1", "ddd_telefone_2",
    "email", "logradouro", "numero", "bairro", "cep", "carregado_em",
]


def _ler_zip(caminho):
    """Itera as linhas (listas) de todos os CSVs de um zip da Receita (latin-1, ';')."""
    with zipfile.ZipFile(caminho) as z:
        for nome in z.namelist():
            with z.open(nome) as bruto:
                texto = io.TextIOWrapper(bruto, encoding="latin-1", newline="")
                yield from csv.reader(texto, delimiter=";", quotechar='"')


def _arquivos(pasta, prefixo):
    achados = sorted(glob.glob(os.path.join(pasta, f"{prefixo}*.zip")) +
                     glob.glob(os.path.join(pasta, f"{prefixo.upper()}*.zip")))
    return sorted(set(achados))


def _telefone(ddd, numero):
    ddd, numero = (ddd or "").strip(), (numero or "").strip()
    return f"{ddd}{numero}" if numero else None


def _corta(valor, tamanho):
    valor = (valor or "").strip()
    return valor[:tamanho] or None


def importar(pasta, ufs, incluir_inativas=False):
    ufs = {u.upper() for u in ufs}
    arq_estab = _arquivos(pasta, "Estabelecimentos")
    arq_emp = _arquivos(pasta, "Empresas")
    arq_mun = _arquivos(pasta, "Municipios")
    if not arq_estab or not arq_emp or not arq_mun:
        sys.exit(f"Faltam arquivos em {pasta}: precisa de Estabelecimentos*.zip, Empresas*.zip e Municipios.zip")

    # 1. Municípios (código Receita -> nome)
    municipios = {}
    for caminho in arq_mun:
        for linha in _ler_zip(caminho):
            if len(linha) >= 2:
                municipios[linha[0].strip()] = linha[1].strip()
    print(f"Municípios: {len(municipios)}")

    # 2. Estabelecimentos da UF -> arquivo temporário; guarda os cnpj_basico usados
    basicos = set()
    tmp = tempfile.NamedTemporaryFile("w", delete=False, encoding="utf-8", newline="", suffix=".csv")
    escritor = csv.writer(tmp)
    total = 0
    for caminho in arq_estab:
        print(f"Lendo {os.path.basename(caminho)}...")
        for c in _ler_zip(caminho):
            if len(c) < 28 or c[19].strip().upper() not in ufs:
                continue
            if not incluir_inativas and c[5].strip() != "02":
                continue
            basicos.add(c[0])
            escritor.writerow(c[:28])
            total += 1
    tmp.close()
    print(f"Estabelecimentos selecionados: {total}")

    # 3. Razão social só dos cnpj_basico selecionados
    razoes = {}
    for caminho in arq_emp:
        print(f"Lendo {os.path.basename(caminho)}...")
        for c in _ler_zip(caminho):
            if len(c) >= 2 and c[0] in basicos:
                razoes[c[0]] = c[1].strip()
    basicos.clear()
    print(f"Empresas encontradas: {len(razoes)}")

    # 4. Grava (substitui as UFs carregadas)
    Base.metadata.create_all(engine, tables=[CnpjBase.__table__])
    agora = datetime.utcnow()

    def linhas():
        with open(tmp.name, encoding="utf-8", newline="") as f:
            for c in csv.reader(f):
                razao = razoes.get(c[0])
                if not razao:
                    continue
                municipio = municipios.get(c[20].strip(), c[20].strip())
                fantasia = c[4].strip()
                yield {
                    "cnpj": f"{c[0]}{c[1]}{c[2]}",
                    "cnpj_basico": c[0],
                    "matriz": c[3].strip() == "1",
                    "razao_social": razao[:255],
                    "razao_normalizada": normalizar(razao)[:255],
                    "razao_raiz": raiz(razao)[:255],
                    "nome_fantasia": fantasia[:255] or None,
                    "fantasia_normalizada": normalizar(fantasia)[:255] or None,
                    "situacao_cadastral": _corta(c[5], 2),
                    "uf": c[19].strip().upper(),
                    "municipio": municipio[:100],
                    "municipio_normalizado": normalizar(municipio)[:100],
                    "cnae_principal": _corta(c[11], 7),
                    "ddd_telefone_1": _telefone(c[21], c[22]),
                    "ddd_telefone_2": _telefone(c[23], c[24]),
                    "email": _corta((c[27] or "").lower(), 255),
                    "logradouro": _corta(f"{c[13]} {c[14]}", 255),
                    "numero": _corta(c[15], 50),
                    "bairro": _corta(c[17], 100),
                    "cep": _corta(c[18], 10),
                    "carregado_em": agora,
                }

    try:
        with engine.begin() as conn:
            conn.execute(delete(CnpjBase).where(CnpjBase.uf.in_(ufs)))
            if engine.dialect.name == "postgresql":
                gravadas = _copy_postgres(conn, linhas())
            else:
                gravadas = _insert_lotes(conn, linhas())
    finally:
        os.unlink(tmp.name)
    print(f"Gravados em cnpj_base: {gravadas} estabelecimentos ({', '.join(sorted(ufs))})")
    return gravadas


def _copy_postgres(conn, linhas):
    """COPY é ordens de grandeza mais rápido que INSERT para milhões de linhas."""
    buffer = io.StringIO()
    escritor = csv.writer(buffer)
    n = 0
    raw = conn.connection.driver_connection
    cursor = raw.cursor()
    sql = f"COPY cnpj_base ({', '.join(COLUNAS)}) FROM STDIN WITH (FORMAT csv)"

    def descarregar():
        buffer.seek(0)
        cursor.copy_expert(sql, buffer)
        buffer.seek(0)
        buffer.truncate()

    for linha in linhas:
        escritor.writerow(["" if linha[c] is None else linha[c] for c in COLUNAS])
        n += 1
        if n % 200_000 == 0:
            descarregar()
            print(f"  {n} linhas...")
    descarregar()
    return n


def _insert_lotes(conn, linhas, tamanho=5_000):
    lote, n = [], 0
    for linha in linhas:
        lote.append(linha)
        if len(lote) >= tamanho:
            conn.execute(insert(CnpjBase), lote)
            n += len(lote)
            lote = []
    if lote:
        conn.execute(insert(CnpjBase), lote)
        n += len(lote)
    return n


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pasta", required=True, help="pasta com os .zip da Receita")
    ap.add_argument("--uf", nargs="+", default=["PR"])
    ap.add_argument("--incluir-inativas", action="store_true", help="carrega também baixadas/inaptas/suspensas")
    args = ap.parse_args()
    importar(args.pasta, args.uf, args.incluir_inativas)


if __name__ == "__main__":
    main()
