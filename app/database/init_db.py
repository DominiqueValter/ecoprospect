import sys
from app.database.connection import engine, Base
from app.models.publicacao import PublicacaoBruta


def init_db():
    print("A conectar à base de dados PostgreSQL...")
    try:
        Base.metadata.create_all(bind=engine)
        print("Tabelas criadas com sucesso na base de dados!")
    except Exception as e:
        print(f"Erro ao ligar ou criar tabelas: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    init_db()