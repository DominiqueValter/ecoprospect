from datetime import datetime
from sqlalchemy import Column, String, Boolean, DateTime, Index
from app.database.connection import Base


class CnpjBase(Base):
    """
    Cópia local (filtrada por UF) dos Dados Abertos do CNPJ da Receita Federal.

    As APIs públicas (BrasilAPI, minhareceita) só consultam POR CNPJ; não buscam
    por razão social. Esta tabela permite resolver "razão social + município -> CNPJ"
    sem raspar buscadores. Carga: app/services/enriquecimento/importar_base_cnpj.py
    """
    __tablename__ = "cnpj_base"

    cnpj = Column(String(14), primary_key=True)
    cnpj_basico = Column(String(8), nullable=False, index=True)
    matriz = Column(Boolean, nullable=False, default=True)

    razao_social = Column(String(255), nullable=False)
    razao_normalizada = Column(String(255), nullable=False)
    razao_raiz = Column(String(255), nullable=False)
    nome_fantasia = Column(String(255), nullable=True)
    fantasia_normalizada = Column(String(255), nullable=True)

    situacao_cadastral = Column(String(2), nullable=True)  # 02 = ATIVA
    uf = Column(String(2), nullable=False)
    municipio = Column(String(100), nullable=True)
    municipio_normalizado = Column(String(100), nullable=True)

    cnae_principal = Column(String(7), nullable=True)
    ddd_telefone_1 = Column(String(20), nullable=True)
    ddd_telefone_2 = Column(String(20), nullable=True)
    email = Column(String(255), nullable=True)
    logradouro = Column(String(255), nullable=True)
    numero = Column(String(50), nullable=True)
    bairro = Column(String(100), nullable=True)
    cep = Column(String(10), nullable=True)

    carregado_em = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        Index("idx_cnpj_base_razao", "uf", "municipio_normalizado", "razao_normalizada"),
        Index("idx_cnpj_base_raiz", "uf", "municipio_normalizado", "razao_raiz"),
        Index("idx_cnpj_base_fantasia", "uf", "municipio_normalizado", "fantasia_normalizada"),
    )
