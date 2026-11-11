from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, Date, DateTime, Boolean, UniqueConstraint, Index
from app.database.connection import Base


class PublicacaoBruta(Base):
    """Modelo ORM para armazenar os dados brutos de matérias do DIOE-PR com auditoria de ingestão."""
    __tablename__ = "publicacoes_brutas"

    id = Column(Integer, primary_key=True, autoincrement=True)
    id_materia = Column(String(50), nullable=False, index=True)
    id_edicao = Column(String(50), nullable=False, index=True)
    numero_edicao = Column(String(50))
    data_edicao = Column(Date, nullable=False, index=True)
    
    orgao = Column(String(255))
    grupo = Column(String(255))
    titulo_sumario = Column(String(500))
    texto_integral = Column(Text, nullable=False)
    
    link_materia = Column(String(500))
    link_edicao_html = Column(String(500))
    link_edicao_pdf = Column(String(500))
    
    hash_conteudo = Column(String(64), nullable=False, unique=True, index=True)
    
    # Compatibilidade mantida com código anterior
    processado = Column(Boolean, default=False, nullable=False, index=True)
    
    # Novos campos de gestão de estados e auditoria de erros (Etapa 1)
    status_processamento = Column(String(50), default="PENDENTE", nullable=False, index=True)  # PENDENTE, PROCESSADA, REVISAO_MANUAL, ERRO
    motivo_revisao = Column(Text, nullable=True)
    processado_em = Column(DateTime, nullable=True)
    
    criado_em = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint('id_materia', 'id_edicao', name='uq_materia_edicao'),
        Index('idx_publicacao_status_data', 'status_processamento', 'data_edicao'),
    )

    def __repr__(self):
        return f"<PublicacaoBruta(id_materia='{self.id_materia}', status='{self.status_processamento}')>"