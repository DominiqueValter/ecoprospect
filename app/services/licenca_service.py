from sqlalchemy.orm import Session
from app.models.licenca import Licenca

def resolver_licenca(db: Session, empresa_id: int, publicacao_id: int, dados_ato: dict) -> tuple[Licenca, bool]:
    """
    Cria ou atualiza uma licença mantendo a integridade sem duplicar.
    Retorna (Licenca, foi_criada_nova)
    """
    numero_licenca = dados_ato.get("numero_licenca", "S/N")
    tipo_licenca = dados_ato.get("tipo_licenca", "LICENÇA")
    municipio = dados_ato.get("municipio", "NÃO INFORMADO")

    # Busca por número da licença + empresa + município
    lic_existente = db.query(Licenca).filter(
        Licenca.empresa_id == empresa_id,
        Licenca.numero_licenca == numero_licenca,
        Licenca.municipio == municipio
    ).first()

    if lic_existente:
        # Atualiza os dados se a publicação for mais recente
        lic_existente.validade = dados_ato.get("validade") or lic_existente.validade
        lic_existente.atividade = dados_ato.get("atividade") or lic_existente.atividade
        lic_existente.endereco_empreendimento = dados_ato.get("endereco") or lic_existente.endereco_empreendimento
        lic_existente.snippet_evidencia = dados_ato.get("snippet_evidencia")
        lic_existente.nivel_confianca_extracao = dados_ato.get("nivel_confianca", 1.0)
        lic_existente.situacao_validacao = dados_ato.get("situacao_validacao", "VALIDADO")
        lic_existente.motivo_revisao_manual = dados_ato.get("motivo_revisao_manual")
        return lic_existente, False

    # Cria Nova Licença
    nova_licenca = Licenca(
        empresa_id=empresa_id,
        publicacao_origem_id=publicacao_id,
        protocolo=dados_ato.get("protocolo"),
        tipo_sumula=f"SÚMULA DE {tipo_licenca}",
        tipo_licenca=tipo_licenca,
        numero_licenca=numero_licenca,
        validade=dados_ato.get("validade"),
        atividade=dados_ato.get("atividade"),
        endereco_empreendimento=dados_ato.get("endereco"),
        municipio=municipio,
        uf=dados_ato.get("uf", "PR"),
        snippet_evidencia=dados_ato.get("snippet_evidencia"),
        nivel_confianca_extracao=dados_ato.get("nivel_confianca", 1.0),
        situacao_validacao=dados_ato.get("situacao_validacao", "VALIDADO"),
        motivo_revisao_manual=dados_ato.get("motivo_revisao_manual")
    )
    db.add(nova_licenca)
    db.flush()
    return nova_licenca, True