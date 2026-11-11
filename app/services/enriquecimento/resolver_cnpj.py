"""
Resolve o CNPJ de uma empresa pela razão social + município, usando a tabela
cnpj_base (Dados Abertos da Receita, ver importar_base_cnpj.py).

Substitui a versão antiga, que raspava o DuckDuckGo: buscadores devolvem desafio
anti-robô (Google/Bing) ou nada (DuckDuckGo), e o resultado vinha sempre vazio.

Ordem de tentativa (sempre dentro da UF e, se houver, do município):
  1. razão social normalizada idêntica
  2. razão social sem forma jurídica (LTDA, ME, EIRELI...) e sem CPF final (MEI)
  3. nome fantasia normalizado
Aceita só quando os candidatos pertencem a UMA empresa (mesmo cnpj_basico);
com mais de uma, devolve REVISAO_IDENTIDADE e lista os CNPJs no motivo.

Uso avulso (só mostra, não grava):
  python -m app.services.enriquecimento.resolver_cnpj "PFD LOTEAMENTOS E INCORPORAÇÕES LTDA" TOLEDO
"""
import sys
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.cnpj_base import CnpjBase
from app.services.enriquecimento.normalizacao import normalizar, raiz

MUNICIPIO_DESCONHECIDO = {"", "NAO INFORMADO"}


@dataclass
class ResultadoResolucao:
    status: str                      # ENCONTRADO, SEM_CNPJ, REVISAO_IDENTIDADE, BASE_VAZIA
    cnpj: str | None = None
    criterio: str | None = None
    motivo: str | None = None
    registro: CnpjBase | None = None
    candidatos: list[str] = field(default_factory=list)


def base_carregada(db: Session, uf: str) -> bool:
    return db.execute(select(CnpjBase.cnpj).where(CnpjBase.uf == uf).limit(1)).first() is not None


def _escolher(registros):
    """Prefere matriz ativa; depois qualquer ativa; depois a primeira."""
    return sorted(
        registros,
        key=lambda r: (r.situacao_cadastral != "02", not r.matriz, r.cnpj),
    )[0]


def resolver_cnpj(db: Session, razao_social: str, municipio: str | None, uf: str = "PR") -> ResultadoResolucao:
    uf = (uf or "PR").upper()
    if not base_carregada(db, uf):
        return ResultadoResolucao(
            status="BASE_VAZIA",
            motivo=f"cnpj_base sem dados da UF {uf}: rode importar_base_cnpj.py",
        )

    mun = normalizar(municipio or "")
    criterios = [
        ("RAZAO_SOCIAL", CnpjBase.razao_normalizada, normalizar(razao_social)),
        ("RAZAO_SEM_FORMA_JURIDICA", CnpjBase.razao_raiz, raiz(razao_social)),
        ("NOME_FANTASIA", CnpjBase.fantasia_normalizada, normalizar(razao_social)),
    ]

    for nome_criterio, coluna, valor in criterios:
        if not valor:
            continue
        consulta = select(CnpjBase).where(CnpjBase.uf == uf, coluna == valor)
        if mun not in MUNICIPIO_DESCONHECIDO:
            consulta = consulta.where(CnpjBase.municipio_normalizado == mun)
        registros = db.execute(consulta.limit(50)).scalars().all()
        if not registros:
            continue

        empresas = {r.cnpj_basico for r in registros}
        if len(empresas) == 1:
            escolhido = _escolher(registros)
            return ResultadoResolucao(
                status="ENCONTRADO",
                cnpj=escolhido.cnpj,
                criterio=nome_criterio,
                registro=escolhido,
                candidatos=[r.cnpj for r in registros],
            )
        cnpjs = sorted(_escolher([r for r in registros if r.cnpj_basico == b]).cnpj for b in empresas)
        return ResultadoResolucao(
            status="REVISAO_IDENTIDADE",
            criterio=nome_criterio,
            motivo=f"{len(empresas)} empresas com o mesmo nome ({nome_criterio}): {', '.join(cnpjs[:10])}",
            candidatos=cnpjs,
        )

    local = f"{municipio}/{uf}" if mun not in MUNICIPIO_DESCONHECIDO else uf
    return ResultadoResolucao(status="SEM_CNPJ", motivo=f"Nome não encontrado na base da Receita em {local}")


def buscar_na_base(db: Session, cnpj: str) -> CnpjBase | None:
    return db.get(CnpjBase, cnpj)


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    from app.database.connection import SessionLocal

    razao = sys.argv[1]
    municipio = sys.argv[2] if len(sys.argv) > 2 else None
    uf = sys.argv[3] if len(sys.argv) > 3 else "PR"
    with SessionLocal() as db:
        r = resolver_cnpj(db, razao, municipio, uf)
    print(f"status={r.status} cnpj={r.cnpj} criterio={r.criterio}")
    if r.motivo:
        print(f"motivo: {r.motivo}")


if __name__ == "__main__":
    main()
