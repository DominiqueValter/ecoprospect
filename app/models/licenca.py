from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, Date, DateTime, Float, ForeignKey, Index
from sqlalchemy.orm import relationship
from app.database.connection import Base


class Licenca(Base):
    """Modelo ORM para o registro consolidado de cada licença emitida com auditoria de evidência."""
    __tablename__ = "licencas"

    id = Column(Integer, primary_key=True, autoincrement=True)
    
    empresa_id = Column(Integer, ForeignKey("empresas.id", ondelete="CASCADE"), nullable=False, index=True)
    publicacao_origem_id = Column(Integer, ForeignKey("publicacoes_brutas.id", ondelete="SET NULL"), nullable=True)

    protocolo = Column(String(50), nullable=True, index=True)
    tipo_sumula = Column(String(255))
    tipo_licenca = Column(String(50), nullable=False, index=True)  # LO, RLO, LP, LI, LAS, AA, LOR, OUTORGA
    numero_licenca = Column(String(100), nullable=False, index=True)
    
    validade = Column(Date, nullable=True, index=True)
    atividade = Column(Text, nullable=True)
    endereco_empreendimento = Column(String(255), nullable=True)
    municipio = Column(String(100), nullable=False, index=True)
    uf = Column(String(2), default="PR")
    
    # Controle temporal de vencimentos (Bloco 3)
    dias_para_vencer = Column(Integer, nullable=True, index=True)
    limite_renovacao_120d = Column(Date, nullable=True)
    situacao_renovacao = Column(String(50), nullable=True, index=True)
    renovacao_publicada_posterior = Column(Text, nullable=True)
    
    # Rastreabilidade de evidência e auditoria de extração (Etapa 1)
    snippet_evidencia = Column(Text, nullable=True)            # Trecho exato do texto do DIOE que originou a extração
    nivel_confianca_extracao = Column(Float, default=1.0)     # Score de 0.0 a 1.0 sobre a qualidade dos dados capturados
    situacao_validacao = Column(String(50), default="VALIDADO", nullable=False, index=True) # VALIDADO, REVISAO_MANUAL, INCOMPLETO
    motivo_revisao_manual = Column(Text, nullable=True)
    
    criado_em = Column(DateTime, default=datetime.utcnow, nullable=False)
    atualizado_em = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    empresa = relationship("Empresa", backref="licencas")
    publicacao_origem = relationship("PublicacaoBruta")

    __table_args__ = (
        Index('idx_licenca_vencimento', 'validade', 'tipo_licenca'),
        Index('idx_licenca_empresa_num', 'empresa_id', 'numero_licenca'),
        Index('idx_licenca_status_renovacao', 'situacao_renovacao', 'dias_para_vencer'),
        Index('idx_licenca_validacao', 'situacao_validacao'),
    )