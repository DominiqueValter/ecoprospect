import sys
from sqlalchemy import text
from app.database.connection import engine

def executar_migracao():
    print("Atualizando tamanho da coluna tipo_sumula para VARCHAR(255)...")
    with engine.connect() as conn:
        try:
            conn.execute(text("""
                ALTER TABLE licencas 
                ALTER COLUMN tipo_sumula TYPE VARCHAR(255);
            """))
            conn.commit()
            print("Sucesso! Coluna 'tipo_sumula' expandida para 255 caracteres.")
        except Exception as e:
            conn.rollback()
            print(f"Erro ao atualizar tabela: {e}", file=sys.stderr)

if __name__ == "__main__":
    executar_migracao()