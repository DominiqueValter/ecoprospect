"""
Agente de enriquecimento (Bloco 5): CNPJ -> dados cadastrais, CNAE e contatos.

Fluxo por empresa (PJ elegível):
  1. CNPJ: usa o da publicação; se não houver, resolve por razão social + município
     na base local da Receita (cnpj_base). Nenhuma API gratuita busca por nome.
  2. Dados: BrasilAPI por CNPJ; se falhar, minhareceita.org por CNPJ; se as duas
     falharem (proxy/firewall), usa os dados da própria cnpj_base.
  3. Grava empresas_enriquecidas + contatos_empresa e commita empresa a empresa
     (uma falha não desfaz as outras).

Estados (empresas_enriquecidas.status_enriquecimento):
  ENRIQUECIDA, SEM_CNPJ, REVISAO_IDENTIDADE, CONSULTA_FALHOU, PENDENTE
O motivo da falha (BLOQUEIO_PROXY, TIMEOUT, HTTP_404...) vai em motivo_estado.

Uso:
  python -m app.services.enriquecimento_contatos              # até 50 pendentes
  python -m app.services.enriquecimento_contatos --limite 200
  python -m app.services.enriquecimento_contatos --reprocessar  # tenta de novo SEM_CNPJ/CONSULTA_FALHOU
  python -m app.services.enriquecimento_contatos --testar-rede  # só diagnostica o acesso às APIs
"""
import argparse
import re
import time
from datetime import datetime

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.database.connection import SessionLocal
from app.models.empresa import Empresa
from app.models.enriquecimento import EmpresaEnriquecida
from app.services.enriquecimento.http_util import get_json
from app.services.enriquecimento.resolver_cnpj import resolver_cnpj, buscar_na_base
from app.services.enriquecimento.salvar_contatos import salvar_contatos
from app.services.titular_service import validar_cnpj

FONTES_CNPJ = [
    ("BRASILAPI", "https://brasilapi.com.br/api/cnpj/v1/{cnpj}"),
    ("MINHARECEITA", "https://minhareceita.org/{cnpj}"),
]
PAUSA_ENTRE_CONSULTAS = 1.5  # BrasilAPI gratuita tem limite de requisições
ESTADOS_REPROCESSAVEIS = ("PENDENTE", "CONSULTA_FALHOU")
ESTADOS_REPROCESSAVEIS_TUDO = ESTADOS_REPROCESSAVEIS + ("SEM_CNPJ", "REVISAO_IDENTIDADE")


def limpar_cnpj(cnpj) -> str | None:
    digitos = re.sub(r"\D", "", str(cnpj or ""))
    return digitos if validar_cnpj(digitos) else None


def consultar_cnpj(cnpj: str):
    """Retorna (dados, fonte, erros). Tenta as fontes em ordem; 404 = CNPJ não existe, não insiste."""
    erros = []
    for fonte, modelo in FONTES_CNPJ:
        dados, erro = get_json(modelo.format(cnpj=cnpj))
        if dados and dados.get("cnpj"):
            return dados, fonte, erros
        erros.append(f"{fonte} {erro or 'resposta sem CNPJ'}")
        if erro and erro.startswith("HTTP_404"):
            break
    return None, None, erros


def dados_da_base(registro) -> dict:
    """Converte uma linha da cnpj_base para o formato da BrasilAPI (sem QSA nem CNAEs secundários)."""
    return {
        "cnpj": registro.cnpj,
        "razao_social": registro.razao_social,
        "nome_fantasia": registro.nome_fantasia,
        "descricao_situacao_cadastral": "ATIVA" if registro.situacao_cadastral == "02" else registro.situacao_cadastral,
        "cnae_fiscal": registro.cnae_principal,
        "cnae_fiscal_descricao": None,
        "cnaes_secundarios": [],
        "logradouro": registro.logradouro,
        "numero": registro.numero,
        "bairro": registro.bairro,
        "cep": registro.cep,
        "ddd_telefone_1": registro.ddd_telefone_1,
        "ddd_telefone_2": registro.ddd_telefone_2,
        "email": registro.email,
        "qsa": [],
    }


def inferir_sinais_ambientais(cnae_principal: str, cnaes_secundarios: list) -> list[str]:
    """Infere POSSÍVEIS necessidades ambientais com base no CNAE."""
    sinais = set()
    todos_cnaes = [str(cnae_principal or "")] + [str(c.get("codigo", "")) for c in (cnaes_secundarios or [])]

    if any(c.startswith(("10", "11", "13", "14", "15", "17", "20", "22", "24", "25")) for c in todos_cnaes):
        sinais.add("POSSIVEL_GERACAO_EFLUENTES_INDUSTRIAIS")
        sinais.add("POSSIVEL_NECESSIDADE_ETE")
    if any(c.startswith(("38", "39", "20", "19")) for c in todos_cnaes):
        sinais.add("POSSIVEL_RESIDUOS_PERIGOSOS_PGRS")
    if any(c.startswith(("41", "42", "43")) for c in todos_cnaes):
        sinais.add("POSSIVEL_RESIDUOS_CONSTRUCAO_CIVIL_PGRCC")
    if any(c.startswith(("01", "02", "03")) for c in todos_cnaes):
        sinais.add("POSSIVEL_NECESSIDADE_OUTORGA_AGUA")

    return sorted(sinais) or ["POSSIVEL_LICENCIAMENTO_PADRAO"]


def _numero(valor) -> float | None:
    try:
        return float(str(valor).replace(",", ".")) if valor not in (None, "") else None
    except ValueError:
        return None


def _aplicar_dados(enr: EmpresaEnriquecida, dados: dict, cnpj: str):
    cnaes_sec = dados.get("cnaes_secundarios") or []
    cnae_p = str(dados.get("cnae_fiscal") or "") or None
    enr.cnpj_limpo = cnpj
    enr.razao_social_oficial = (dados.get("razao_social") or "")[:255] or None
    enr.nome_fantasia = (dados.get("nome_fantasia") or "")[:255] or None
    enr.situacao_cadastral = (dados.get("descricao_situacao_cadastral") or "")[:50] or None
    enr.cnae_principal_codigo = cnae_p[:10] if cnae_p else None
    enr.cnae_principal_descricao = (dados.get("cnae_fiscal_descricao") or "")[:255] or None
    enr.cnaes_secundarios = cnaes_sec
    enr.porte = (dados.get("porte") or "")[:50] or None
    enr.capital_social = _numero(dados.get("capital_social"))
    enr.logradouro = (dados.get("logradouro") or "")[:255] or None
    enr.numero = (dados.get("numero") or "")[:50] or None
    enr.bairro = (dados.get("bairro") or "")[:100] or None
    enr.cep = (dados.get("cep") or "")[:10] or None
    enr.sinais_ambientais_inferidos = inferir_sinais_ambientais(cnae_p, cnaes_sec)


def enriquecer_empresa(db: Session, emp: Empresa, pausa: float = PAUSA_ENTRE_CONSULTAS) -> str:
    """Processa uma empresa e devolve o estado final. Não faz commit."""
    enr = db.query(EmpresaEnriquecida).filter(EmpresaEnriquecida.empresa_id == emp.id).first()
    if enr is None:
        enr = EmpresaEnriquecida(empresa_id=emp.id, razao_social_oficial=emp.razao_social)
        db.add(enr)
    enr.ultima_tentativa_em = datetime.utcnow()

    # 1. CNPJ
    cnpj = limpar_cnpj(emp.cnpj) or limpar_cnpj(enr.cnpj_limpo)
    registro_base = None
    if not cnpj:
        r = resolver_cnpj(db, emp.razao_social, emp.municipio, emp.uf or "PR")
        if r.status != "ENCONTRADO":
            enr.status_enriquecimento = "PENDENTE" if r.status == "BASE_VAZIA" else r.status
            enr.motivo_estado = r.motivo
            return enr.status_enriquecimento
        cnpj, registro_base = r.cnpj, r.registro
        emp.cnpj = cnpj
        print(f"  [+] CNPJ {cnpj} identificado na base da Receita ({r.criterio})")

    # 2. Dados cadastrais
    dados, fonte, erros = consultar_cnpj(cnpj)
    if pausa:
        time.sleep(pausa)
    motivo = None
    if not dados:
        registro_base = registro_base or buscar_na_base(db, cnpj)
        if registro_base is None:
            enr.cnpj_limpo = cnpj
            enr.status_enriquecimento = "CONSULTA_FALHOU"
            enr.motivo_estado = " | ".join(erros)[:2000]
            return enr.status_enriquecimento
        dados, fonte = dados_da_base(registro_base), "RECEITA_DADOS_ABERTOS"
        motivo = "APIs indisponíveis, usados dados da base local: " + " | ".join(erros)

    # 3. Gravação
    _aplicar_dados(enr, dados, cnpj)
    novos = salvar_contatos(db, emp.id, dados, fonte="RECEITA_FEDERAL" if fonte != "RECEITA_DADOS_ABERTOS" else fonte)
    enr.status_enriquecimento = "ENRIQUECIDA"
    enr.motivo_estado = (motivo or f"Fonte: {fonte}")[:2000]
    print(f"  [ok] {novos} contatos novos (fonte {fonte})")
    return enr.status_enriquecimento


def selecionar_pendentes(db: Session, limite: int, reprocessar: bool):
    estados = ESTADOS_REPROCESSAVEIS_TUDO if reprocessar else ESTADOS_REPROCESSAVEIS
    return (
        db.query(Empresa)
        .outerjoin(EmpresaEnriquecida, Empresa.id == EmpresaEnriquecida.empresa_id)
        .filter(
            Empresa.tipo_titular == "PJ",
            Empresa.elegivel_prospeccao == "ELEGIVEL",
            Empresa.razao_social != "NÃO INFORMADO",
            or_(
                EmpresaEnriquecida.id.is_(None),
                EmpresaEnriquecida.status_enriquecimento.in_(estados),
            ),
        )
        .order_by(Empresa.id)
        .limit(limite)
        .all()
    )


def enriquecer_empresas_base(limite: int = 50, reprocessar: bool = False) -> dict:
    db: Session = SessionLocal()
    print("Iniciando Agente de Enriquecimento Empresarial (Bloco 5)...")
    contagem: dict[str, int] = {}
    try:
        empresas = selecionar_pendentes(db, limite, reprocessar)
        if not empresas:
            print("Nenhuma empresa pendente para enriquecimento no momento.")
            return contagem
        print(f"Encontradas {len(empresas)} empresas para enriquecer...")

        for n, emp in enumerate(empresas, start=1):
            print(f"[{n}/{len(empresas)}] {emp.razao_social} — {emp.municipio}/{emp.uf}")
            try:
                estado = enriquecer_empresa(db, emp)
                db.commit()
            except Exception as e:  # noqa: BLE001 - registra e segue para a próxima
                db.rollback()
                estado = "ERRO_INTERNO"
                print(f"  [x] {type(e).__name__}: {e}")
            contagem[estado] = contagem.get(estado, 0) + 1
            if estado != "ENRIQUECIDA":
                enr = db.query(EmpresaEnriquecida).filter(EmpresaEnriquecida.empresa_id == emp.id).first()
                if enr and enr.motivo_estado:
                    print(f"  [-] {estado}: {enr.motivo_estado}")

        print("Resumo: " + ", ".join(f"{k}={v}" for k, v in sorted(contagem.items())))
        return contagem
    finally:
        db.close()


def testar_rede():
    """Mostra se as APIs respondem deste computador e, se não, por quê."""
    cnpj_teste = "33000167000101"  # Petrobras, sempre existe
    for fonte, modelo in FONTES_CNPJ:
        dados, erro = get_json(modelo.format(cnpj=cnpj_teste))
        print(f"{fonte:13} {'OK' if dados else erro}")


def main():
    ap = argparse.ArgumentParser(description="Enriquecimento de empresas (Bloco 5)")
    ap.add_argument("--limite", type=int, default=50)
    ap.add_argument("--reprocessar", action="store_true", help="inclui SEM_CNPJ e REVISAO_IDENTIDADE")
    ap.add_argument("--testar-rede", action="store_true")
    args = ap.parse_args()
    if args.testar_rede:
        testar_rede()
    else:
        enriquecer_empresas_base(args.limite, args.reprocessar)


if __name__ == "__main__":
    main()
