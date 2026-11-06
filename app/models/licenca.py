from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, Date, DateTime, ForeignKey, Index
from sqlalchemy.orm import relationship
from app.database.connection import Base


class Licenca(Base):
    """Modelo ORM para o registro consolidado de cada licença emitida pelo IAT."""
    __tablename__ = "licencas"

    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Vínculo com a empresa (Chave Estrangeira)
    empresa_id = Column(Integer, ForeignKey("empresas.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Vínculo com a publicação de origem no DIOE (Chave Estrangeira)
    publicacao_origem_id = Column(Integer, ForeignKey("publicacoes_brutas.id", ondelete="SET NULL"), nullable=True)

    protocolo = Column(String(50), nullable=True, index=True)
    tipo_sumula = Column(String(100))  # Ex: CONCESSÃO DE RENOVAÇÃO DA LICENÇA DE OPERAÇÃO
    tipo_licenca = Column(String(50), nullable=False, index=True)  # LO, RLO, LP, LI, LAS, AA
    numero_licenca = Column(String(100), nullable=False, index=True)
    
    validade = Column(Date, nullable=True, index=True)
    atividade = Column(Text, nullable=True)
    endereco_empreendimento = Column(String(255), nullable=True)
    municipio = Column(String(100), nullable=False, index=True)
    uf = Column(String(2), default="PR")
    
    criado_em = Column(DateTime, default=datetime.utcnow, nullable=False)
    atualizado_em = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relacionamentos ORM
    empresa = relationship("Empresa", backref="licencas")
    publicacao_origem = relationship("PublicacaoBruta")

    __table_args__ = (
        Index('idx_licenca_vencimento', 'validade', 'tipo_licenca'),
        Index('idx_licenca_empresa_num', 'empresa_id', 'numero_licenca'),
    )