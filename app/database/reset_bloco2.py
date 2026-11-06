from sqlalchemy import text
from app.database.connection import engine

def resetar_bloco2():
    print("Limpando tabelas empresas e licencas para reprocessamento...")
    with engine.connect() as conn:
        conn.execute(text("TRUNCATE TABLE licencas, empresas RESTART IDENTITY CASCADE;"))
        conn.execute(text("UPDATE publicacoes_brutas SET processado = FALSE;"))
        conn.commit()
    print("Tabelas resetadas com sucesso!")

if __name__ == "__main__":
    resetar_bloco2()