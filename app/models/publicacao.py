from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, Date, DateTime, UniqueConstraint
from app.database.connection import Base


class PublicacaoBruta(Base):
    """Modelo ORM para armazenar os dados brutos de matérias do DIOE-PR."""
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
    criado_em = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint('id_materia', 'id_edicao', name='uq_materia_edicao'),
    )

    def __repr__(self):
        return f"<PublicacaoBruta(id_materia='{self.id_materia}', data_edicao='{self.data_edicao}')>"