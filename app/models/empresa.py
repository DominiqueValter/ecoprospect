from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Index
from app.database.connection import Base


class Empresa(Base):
    """Modelo ORM para armazenar estabelecimentos jurídicos, pessoas físicas e órgãos públicos titulares."""
    __tablename__ = "empresas"

    id = Column(Integer, primary_key=True, autoincrement=True)
    razao_social = Column(String(255), nullable=False, index=True)
    razao_social_normalizada = Column(String(255), nullable=False, index=True)
    
    # Distinção estrita de titularidade (Etapa 1)
    tipo_titular = Column(String(50), default="PJ", nullable=False, index=True)  # PJ, PF, ORGAO_PUBLICO, INDETERMINADO
    cnpj = Column(String(18), nullable=True, index=True)  # Apenas CNPJ formatado ou limpo (14 dígitos)
    cpf = Column(String(14), nullable=True, index=True)   # Apenas CPF formatado ou limpo (11 dígitos)
    
    municipio = Column(String(100), nullable=False, index=True)
    uf = Column(String(2), default="PR", nullable=False)
    endereco_padrao = Column(String(255), nullable=True)
    
    # Status de elegibilidade para prospecção comercial B2B
    elegivel_prospeccao = Column(String(50), default="ELEGIVEL", nullable=False, index=True)  # ELEGIVEL, PF_IGNORADA_B2B, ORGAO_IGNORADO, REVISAO_MANUAL
    
    criado_em = Column(DateTime, default=datetime.utcnow, nullable=False)
    atualizado_em = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    __table_args__ = (
        Index('idx_empresa_busca', 'razao_social_normalizada', 'municipio'),
        Index('idx_empresa_tipo_elegibilidade', 'tipo_titular', 'elegivel_prospeccao'),
    )