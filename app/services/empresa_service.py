import re
from sqlalchemy.orm import Session
from app.models.empresa import Empresa
from app.services.titular_service import identificar_tipo_titular

def normalizar_nome(nome: str) -> str:
    if not nome:
        return ""
    nome_clean = re.sub(r"[^\w\s]", " ", nome.upper())
    return " ".join(nome_clean.split())

def resolver_titular(db: Session, dados_ato: dict) -> tuple[Empresa, str]:
    """
    Localiza ou cadastra o titular (PJ, PF ou Órgão Público).
    Retorna (Empresa, status_resolucao)
    """
    titular_raw = dados_ato.get("titular")
    if not titular_raw:
        return None, "INDETERMINADO"

    razao_norm = normalizar_nome(titular_raw)
    municipio = (dados_ato.get("municipio") or "NÃO INFORMADO").upper()
    uf = (dados_ato.get("uf") or "PR").upper()
    cnpj = dados_ato.get("cnpj")
    cpf = dados_ato.get("cpf")
    tipo_titular = dados_ato.get("tipo_titular", "PJ")
    elegibilidade = dados_ato.get("elegibilidade_b2b", "ELEGIVEL")

    # 1. Busca priorizando CNPJ (PJ)
    if cnpj:
        emp = db.query(Empresa).filter(Empresa.cnpj == cnpj).first()
        if emp:
            return emp, "ENCONTRADO_POR_CNPJ"

    # 2. Busca priorizando CPF (PF)
    if cpf:
        emp = db.query(Empresa).filter(Empresa.cpf == cpf).first()
        if emp:
            return emp, "ENCONTRADO_POR_CPF"

    # 3. Busca por Razão Social Normalizada + Município
    emp = db.query(Empresa).filter(
        Empresa.razao_social_normalizada == razao_norm,
        Empresa.municipio == municipio
    ).first()

    if emp:
        # Se encontrou e agora temos CNPJ/CPF que faltava, atualiza
        if cnpj and not emp.cnpj:
            emp.cnpj = cnpj
        if cpf and not emp.cpf:
            emp.cpf = cpf
        return emp, "ENCONTRADO_POR_NOME"

    # 4. Cadastra Novo Titular
    nova_empresa = Empresa(
        razao_social=titular_raw,
        razao_social_normalizada=razao_norm,
        tipo_titular=tipo_titular,
        cnpj=cnpj,
        cpf=cpf,
        municipio=municipio,
        uf=uf,
        endereco_padrao=dados_ato.get("endereco"),
        elegivel_prospeccao=elegibilidade
    )
    db.add(nova_empresa)
    db.flush()
    return nova_empresa, "CRIADO_NOVO"