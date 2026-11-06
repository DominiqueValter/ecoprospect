import sys
from sqlalchemy import text
from app.database.connection import engine


def executar_migracao():
    print("Executando atualização na tabela publicacoes_brutas...")
    with engine.connect() as conn:
        try:
            # Adiciona a coluna processado com valor padrão False caso ela não exista
            conn.execute(text("""
                ALTER TABLE publicacoes_brutas 
                ADD COLUMN IF NOT EXISTS processado BOOLEAN NOT NULL DEFAULT FALSE;
            """))
            
            # Criar o índice de busca rápida para pendentes
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_publicacao_pendente 
                ON publicacoes_brutas (processado, data_edicao);
            """))
            
            conn.commit()
            print("Sucesso! Coluna 'processado' e índices adicionados à tabela 'publicacoes_brutas'.")
        except Exception as e:
            conn.rollback()
            print(f"Erro ao atualizar tabela: {e}", file=sys.stderr)


if __name__ == "__main__":
    executar_migracao()