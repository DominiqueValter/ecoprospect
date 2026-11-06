from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Index
from app.database.connection import Base


class Empresa(Base):
    """Modelo ORM para armazenar os estabelecimentos jurídicos/empresas."""
    __tablename__ = "empresas"

    id = Column(Integer, primary_key=True, autoincrement=True)
    razao_social = Column(String(255), nullable=False, index=True)
    razao_social_normalizada = Column(String(255), nullable=False, index=True)
    cnpj = Column(String(18), nullable=True, index=True)  # CNPJ formatado ou limpo
    
    municipio = Column(String(100), nullable=False, index=True)
    uf = Column(String(2), default="PR", nullable=False)
    endereco_padrao = Column(String(255), nullable=True)
    
    criado_em = Column(DateTime, default=datetime.utcnow, nullable=False)
    atualizado_em = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    __table_args__ = (
        Index('idx_empresa_busca', 'razao_social_normalizada', 'municipio'),
    )