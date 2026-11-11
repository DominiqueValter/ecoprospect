"""
Grava telefones, e-mail e sócios (QSA) em contatos_empresa.

Correções em relação à versão anterior:
- importava app.models.contato (não existe): o modelo está em app.models.enriquecimento;
- usava os campos origem/principal (não existem): o modelo tem fonte_informacao
  (obrigatório), nivel_confianca e e_contato_direto_comercial;
- lia telefone1/nome/qualificacao: a BrasilAPI e a minhareceita devolvem
  ddd_telefone_1, nome_socio e qualificacao_socio;
- não deduplicava: rodar duas vezes duplicava os contatos.
"""
import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enriquecimento import ContatoEmpresa


def _telefone_limpo(valor) -> str | None:
    digitos = re.sub(r"\D", "", str(valor or ""))
    return digitos if len(digitos) >= 10 else None


def _ja_existe(db: Session, empresa_id: int, tipo: str, valor: str) -> bool:
    consulta = select(ContatoEmpresa.id).where(
        ContatoEmpresa.empresa_id == empresa_id,
        ContatoEmpresa.tipo_contato == tipo,
        ContatoEmpresa.valor == valor,
    )
    return db.execute(consulta).first() is not None


def _adicionar(db, empresa_id, tipo, valor, fonte, confianca, direto=True, nome=None, cargo=None) -> int:
    valor = (valor or "").strip()[:255]
    if not valor or _ja_existe(db, empresa_id, tipo, valor):
        return 0
    db.add(ContatoEmpresa(
        empresa_id=empresa_id,
        tipo_contato=tipo,
        valor=valor,
        nome_responsavel=nome,
        cargo_funcao=(cargo or None) and cargo[:100],
        fonte_informacao=fonte,
        nivel_confianca=confianca,
        e_contato_direto_comercial=direto,
    ))
    db.flush()
    return 1


def salvar_contatos(db: Session, empresa_id: int, dados: dict, fonte: str = "RECEITA_FEDERAL") -> int:
    """
    `dados` no formato da BrasilAPI/minhareceita (ou o dict montado a partir da cnpj_base).
    Não faz commit: quem chama controla a transação. Retorna quantos contatos novos gravou.
    """
    novos = 0

    email = (dados.get("email") or "").strip().lower()
    if email and "@" in email:
        novos += _adicionar(db, empresa_id, "EMAIL", email, fonte, 85)

    for chave in ("ddd_telefone_1", "ddd_telefone_2"):
        tel = _telefone_limpo(dados.get(chave))
        if tel:
            novos += _adicionar(db, empresa_id, "TELEFONE", tel, fonte, 90)

    for socio in dados.get("qsa") or []:
        nome = (socio.get("nome_socio") or socio.get("nome") or "").strip()
        if not nome:
            continue
        cargo = (socio.get("qualificacao_socio") or socio.get("qualificacao") or "").strip()
        novos += _adicionar(
            db, empresa_id, "SOCIO_QSA", nome, f"{fonte}_QSA", 95,
            direto=False, nome=nome, cargo=cargo,
        )

    return novos


def salvar_contatos_extraidos(empresa_id: int, dados_api: dict) -> int:
    """Compatibilidade com a assinatura antiga: abre a própria sessão e faz commit."""
    from app.database.connection import SessionLocal

    db = SessionLocal()
    try:
        novos = salvar_contatos(db, empresa_id, dados_api)
        db.commit()
        print(f"Sucesso: {novos} contatos salvos para a empresa ID {empresa_id}.")
        return novos
    except Exception as e:
        db.rollback()
        print(f"Erro ao salvar contatos da empresa ID {empresa_id}: {e}")
        return 0
    finally:
        db.close()
