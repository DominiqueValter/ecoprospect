import re
from sqlalchemy.orm import Session
from app.database.connection import SessionLocal
from app.models.licenca import Licenca
from app.models.empresa import Empresa
from app.models.oportunidade import Oportunidade

# Configurações do Tenant Atakama (Área de Atuação e Catálogo)
MUNICIPIOS_ATENDIDOS_ATAKAMA = [
    "CURITIBA", "SAO JOSE DOS PINHAIS", "COLOMBO", "ARAUCARIA", "PINHAIS",
    "CAMPO LARGO", "ALMIRANTE TAMANDARE", "FAZENDA RIO GRANDE", "CAMPO MAGRO",
    "PIRAQUARA", "QUATRO BARRAS", "CAMPINA GRANDE DO SUL", "MANDIRITUBA",
    "PARANAGUA", "CASTRO", "PONTA GROSSA", "GUARAPUAVA"
]

SERVICOS_ATAKAMA = {
    "RENOVACAO_LO": "Assessoria para Renovação de Licença de Operação (LO/RLO)",
    "PGRS": "Plano de Gerenciamento de Resíduos Sólidos (PGRS)",
    "PGRCC": "Plano de Gerenciamento de Resíduos da Construção Civil (PGRCC)",
    "OUTORGA": "Outorga de Recursos Hídricos e Diagnóstico de Efluentes",
    "ETE": "Projeto e Monitoramento de Estação de Tratamento de Efluentes (ETE)",
    "GESTAO_OBRAS": "Licenciamento, Gestão Ambiental e Monitoramento de Obras (LP/LI)",
    "RUIDO": "Laudos e Medições de Ruído Ambiental",
    "REGULARIZACAO": "Regularização Ambiental e Licença de Operação de Regularização (LOR)"
}


def classificar_evento(lic: Licenca) -> str:
    """Classifica o evento ambiental com base no tipo da súmula e tipo da licença."""
    tipo = (lic.tipo_licenca or "").upper()
    sumula = (lic.tipo_sumula or "").upper()

    if "RENOVACAO" in sumula or "RLO" in tipo:
        return "RENOVACAO_LICENCA"
    elif "AMPLIACAO" in sumula or "LAS-A" in tipo or "LO-A" in tipo:
        return "AMPLIACAO_EMPREENDIMENTO"
    elif "PRORROGACAO" in sumula:
        return "PRORROGACAO_LICENCA"
    elif "OUTORGA" in tipo or "PORTARIA" in tipo or "RECURSOS HIDRICOS" in sumula:
        return "OUTORGA_RECURSOS_HIDRICOS"
    elif "PREVIA" in sumula or "LP" in tipo:
        return "CONCESSAO_LP"
    elif "INSTALACAO" in sumula or "LI" in tipo:
        return "CONCESSAO_LI"
    elif "REGULARIZACAO" in sumula or "LOR" in tipo:
        return "REGULARIZACAO_AMBIENTAL"
    elif "CANCELADO" in sumula or "INDEFERIDO" in sumula:
        return "INDEFERIMENTO_CANCELAMENTO"
    else:
        return "CONCESSAO_LICENCA"


def mapear_servicos_recomendados(lic: Licenca, tipo_evento: str) -> list[str]:
    """Associa as necessidades ambientais aos serviços do catálogo da Atakama."""
    servicos = []
    atividade = (lic.atividade or "").upper()

    # Regras por Evento
    if tipo_evento in ["RENOVACAO_LICENCA", "CONCESSAO_LICENCA"]:
        servicos.append(SERVICOS_ATAKAMA["RENOVACAO_LO"])
    elif tipo_evento in ["CONCESSAO_LP", "CONCESSAO_LI", "AMPLIACAO_EMPREENDIMENTO"]:
        servicos.append(SERVICOS_ATAKAMA["GESTAO_OBRAS"])
        servicos.append(SERVICOS_ATAKAMA["PGRCC"])
    elif tipo_evento == "OUTORGA_RECURSOS_HIDRICOS":
        servicos.append(SERVICOS_ATAKAMA["OUTORGA"])
        servicos.append(SERVICOS_ATAKAMA["ETE"])
    elif tipo_evento == "REGULARIZACAO_AMBIENTAL":
        servicos.append(SERVICOS_ATAKAMA["REGULARIZACAO"])

    # Regras por Atividade
    if any(p in atividade for p in ["RESIDUO", "LIXO", "SUINOCULTURA", "AGROPECUARIA", "COMERCIO"]):
        servicos.append(SERVICOS_ATAKAMA["PGRS"])
    if any(p in atividade for p in ["EFLUENTE", "LAVADOR", "POSTO", "EFLUENTES", "AGUA"]):
        servicos.append(SERVICOS_ATAKAMA["ETE"])
    if "OBRA" in atividade or "CONSTRUCAO" in atividade or "EDIFICACOES" in atividade:
        servicos.append(SERVICOS_ATAKAMA["PGRCC"])
        servicos.append(SERVICOS_ATAKAMA["RUIDO"])

    # Remove duplicados mantendo a ordem
    return list(dict.fromkeys(servicos))


def calcular_scoring(lic: Licenca, servicos: list[str]) -> tuple[int, int, int, str]:
    """Calcula o Score de 0 a 100 (Urgência + Compatibilidade)."""
    score_urgencia = 0
    score_compat = 0
    justificativa = []

    # 1. Pontuação de Urgência Temporal (Até 60 pontos)
    dias = lic.dias_para_vencer
    situacao = lic.situacao_renovacao

    if situacao == "DENTRO_PRAZO_120D":
        if dias is not None and 90 <= dias <= 150:
            score_urgencia = 60
            justificativa.append("Janela de ouro: faltam entre 90 e 150 dias para vencer (Prazo de 120 dias).")
        else:
            score_urgencia = 45
            justificativa.append("Dentro do prazo limite de 120 dias para solicitar renovação.")
    elif situacao == "PRAZO_120D_PASSOU":
        score_urgencia = 55
        justificativa.append("Urgência alta: prazo de 120 dias já expirou, licença precisa de protocolo rápido.")
    elif situacao == "EXPIRADA":
        score_urgencia = 50
        justificativa.append("Licença expirada: oportunidade de Regularização Ambiental (LOR).")
    else:
        score_urgencia = 20
        justificativa.append("Licença recente ou com prazo longo de vigência.")

    # 2. Pontuação de Compatibilidade de Serviços (Até 40 pontos)
    qtd_servicos = len(servicos)
    if qtd_servicos >= 3:
        score_compat = 40
        justificativa.append(f"Alta sinergia: {qtd_servicos} serviços compatíveis identificados.")
    elif qtd_servicos == 2:
        score_compat = 30
        justificativa.append(f"Média sinergia: {qtd_servicos} serviços compatíveis identificados.")
    elif qtd_servicos == 1:
        score_compat = 20
        justificativa.append(f"Sinergia pontual: 1 serviço compatível identificado.")

    score_total = min(100, score_urgencia + score_compat)
    return score_total, score_urgencia, score_compat, " | ".join(justificativa)


def avaliar_oportunidades():
    db: Session = SessionLocal()
    print("Iniciando avaliação e qualificação comercial de oportunidades (Bloco 4)...")

    try:
        licencas = db.query(Licenca).all()
        if not licencas:
            print("Nenhuma licença encontrada no banco para qualificar.")
            return 0

        novas_ops = 0
        atualizadas = 0

        for lic in licencas:
            empresa = lic.empresa
            tipo_evento = classificar_evento(lic)
            servicos = mapear_servicos_recomendados(lic, tipo_evento)

            # --- AVALIAÇÃO DOS 5 CRITÉRIOS OBRIGATÓRIOS ---
            crit_1_evento = bool(tipo_evento)
            crit_2_empresa = bool(empresa and empresa.razao_social_normalizada and empresa.razao_social != "NÃO INFORMADO")
            crit_3_servico = len(servicos) > 0
            crit_4_localizacao = (empresa.municipio or "").upper() in MUNICIPIOS_ATENDIDOS_ATAKAMA
            crit_5_evidencia = bool(lic.numero_licenca and lic.numero_licenca != "S/N")

            todos_ok = crit_1_evento and crit_2_empresa and crit_3_servico and crit_4_localizacao and crit_5_evidencia

            # Regra de Descarte: Se já existe renovação posterior publicada no IAT
            if lic.renovacao_publicada_posterior:
                status_final = "DESCARTO_JA_RENOVOU"
            elif todos_ok:
                status_final = "AUTOMATICA"
            else:
                status_final = "FILA_TRIAGEM"

            score_total, score_urg, score_comp, justificativa = calcular_scoring(lic, servicos)

            # Evidência pública detalhada
            validade_str = lic.validade.strftime("%d/%m/%Y") if lic.validade else "NÃO INFORMADA"
            evidencia = f"Licença {lic.numero_licenca} ({lic.tipo_licenca}) - Validade: {validade_str} - Município: {lic.municipio}"

            # Evita duplicidade de oportunidades para a mesma licença
            op_existente = db.query(Oportunidade).filter(Oportunidade.licenca_id == lic.id).first()

            if not op_existente:
                nova_op = Oportunidade(
                    empresa_id=empresa.id,
                    licenca_id=lic.id,
                    publicacao_id=lic.publicacao_origem_id,
                    tipo_evento=tipo_evento,
                    score_total=score_total,
                    score_urgencia=score_urg,
                    score_compatibilidade=score_comp,
                    crit_evento_ok=crit_1_evento,
                    crit_empresa_ok=crit_2_empresa,
                    crit_servico_ok=crit_3_servico,
                    crit_localizacao_ok=crit_4_localizacao,
                    crit_evidencia_ok=crit_5_evidencia,
                    todos_criterios_ok=todos_ok,
                    status=status_final,
                    servicos_recomendados=servicos,
                    justificativa_score=justificativa,
                    evidencia_publica=evidencia
                )
                db.add(nova_op)
                novas_ops += 1
            else:
                op_existente.score_total = score_total
                op_existente.score_urgencia = score_urg
                op_existente.score_compatibilidade = score_comp
                op_existente.status = status_final
                op_existente.servicos_recomendados = servicos
                op_existente.justificativa_score = justificativa
                atualizadas += 1

        db.commit()
        print(f"Sucesso! {novas_ops} novas oportunidades qualificadas | {atualizadas} atualizadas.")
        return novas_ops

    except Exception as e:
        db.rollback()
        print(f"Erro ao processar inteligência comercial: {e}")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    avaliar_oportunidades()