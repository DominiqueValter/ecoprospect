from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, Float, Boolean, ForeignKey, JSON, Index
from sqlalchemy.orm import relationship
from app.database.connection import Base


class EmpresaEnriquecida(Base):
    """Modelo ORM para dados cadastrais profundos com controle explícito de máquina de estados."""
    __tablename__ = "empresas_enriquecidas"

    id = Column(Integer, primary_key=True, autoincrement=True)
    empresa_id = Column(Integer, ForeignKey("empresas.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)

    # Máquina de estados explícita do enriquecimento (Etapa 1)
    status_enriquecimento = Column(String(50), default="PENDENTE", nullable=False, index=True)  # PENDENTE, SEM_CNPJ, CONSULTA_FALHOU, ENRIQUECIDA, REVISAO_IDENTIDADE
    motivo_estado = Column(Text, nullable=True)

    cnpj_limpo = Column(String(14), nullable=True, index=True)
    razao_social_oficial = Column(String(255), nullable=True)
    nome_fantasia = Column(String(255), nullable=True)
    situacao_cadastral = Column(String(50), nullable=True)
    
    cnae_principal_codigo = Column(String(10), nullable=True, index=True)
    cnae_principal_descricao = Column(String(255), nullable=True)
    cnaes_secundarios = Column(JSON, nullable=True)
    
    porte = Column(String(50), nullable=True)
    capital_social = Column(Float, nullable=True)
    
    logradouro = Column(String(255), nullable=True)
    numero = Column(String(50), nullable=True)
    bairro = Column(String(100), nullable=True)
    cep = Column(String(10), nullable=True)
    
    sinais_ambientais_inferidos = Column(JSON, nullable=True)
    
    ultima_tentativa_em = Column(DateTime, default=datetime.utcnow, nullable=False)
    criado_em = Column(DateTime, default=datetime.utcnow, nullable=False)
    atualizado_em = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    empresa = relationship("Empresa", backref="dados_enriquecidos")


class ContatoEmpresa(Base):
    """Modelo ORM para contatos comerciais públicos com separação de canais de sócios QSA."""
    __tablename__ = "contatos_empresa"

    id = Column(Integer, primary_key=True, autoincrement=True)
    empresa_id = Column(Integer, ForeignKey("empresas.id", ondelete="CASCADE"), nullable=False, index=True)

    tipo_contato = Column(String(50), nullable=False)  # TELEFONE, WHATSAPP, EMAIL, WEBSITE, SOCIO_QSA
    valor = Column(String(255), nullable=False)
    nome_responsavel = Column(String(255), nullable=True)
    cargo_funcao = Column(String(100), nullable=True)
    
    fonte_informacao = Column(String(255), nullable=False)
    nivel_confianca = Column(Integer, default=100)
    e_contato_direto_comercial = Column(Boolean, default=True, nullable=False) # False para sócios QSA informativos
    
    data_pesquisa = Column(DateTime, default=datetime.utcnow, nullable=False)

    empresa = relationship("Empresa", backref="contatos")

    __table_args__ = (
        Index('idx_contato_empresa_tipo', 'empresa_id', 'tipo_contato'),
    )