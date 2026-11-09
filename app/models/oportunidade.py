from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey, JSON, Index
from sqlalchemy.orm import relationship
from app.database.connection import Base


class Oportunidade(Base):
    """Modelo ORM para armazenar as oportunidades comerciais qualificadas pelo Bloco 4."""
    __tablename__ = "oportunidades"

    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Vínculos
    empresa_id = Column(Integer, ForeignKey("empresas.id", ondelete="CASCADE"), nullable=False, index=True)
    licenca_id = Column(Integer, ForeignKey("licencas.id", ondelete="CASCADE"), nullable=True, index=True)
    publicacao_id = Column(Integer, ForeignKey("publicacoes_brutas.id", ondelete="SET NULL"), nullable=True)

    # Classificação do Evento Ambiental
    tipo_evento = Column(String(100), nullable=False, index=True) # CONCESSAO, RENOVAÇÃO, AMPLIACAO, OUTORGA, REGULARIZACAO, CONDICIONANTE
    
    # Scoring Comercial (0 a 100)
    score_total = Column(Integer, nullable=False, default=0, index=True)
    score_urgencia = Column(Integer, default=0)
    score_compatibilidade = Column(Integer, default=0)
    
    # Validação dos 5 Critérios Obrigatórios
    crit_evento_ok = Column(Boolean, default=False)
    crit_empresa_ok = Column(Boolean, default=False)
    crit_servico_ok = Column(Boolean, default=False)
    crit_localizacao_ok = Column(Boolean, default=False)
    crit_evidencia_ok = Column(Boolean, default=False)
    todos_criterios_ok = Column(Boolean, default=False, index=True)

    # Status da Oportunidade
    status = Column(String(50), nullable=False, default="FILA_TRIAGEM", index=True) # AUTOMATICA, FILA_TRIAGEM, DESCARTO_JA_RENOVOU, REJEITADA_MANUAL
    
    # Recomendações e Evidências
    servicos_recomendados = Column(JSON, nullable=True) # Ex: ["Renovação de LO", "PGRS", "Outorga"]
    justificativa_score = Column(Text, nullable=True)
    evidencia_publica = Column(Text, nullable=True)
    
    criado_em = Column(DateTime, default=datetime.utcnow, nullable=False)
    atualizado_em = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    empresa = relationship("Empresa", backref="oportunidades")
    licenca = relationship("Licenca", backref="oportunidades")
    publicacao = relationship("PublicacaoBruta")

    __table_args__ = (
        Index('idx_oportunidade_status_score', 'status', 'score_total'),
        Index('idx_oportunidade_empresa_evento', 'empresa_id', 'tipo_evento'),
    )