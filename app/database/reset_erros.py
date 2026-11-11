from app.database.connection import SessionLocal
from app.models.publicacao import PublicacaoBruta

def resetar_erros():
    db = SessionLocal()
    try:
        qtd = db.query(PublicacaoBruta).filter(PublicacaoBruta.status_processamento == "ERRO").update(
            {PublicacaoBruta.status_processamento: "PENDENTE", PublicacaoBruta.motivo_revisao: None},
            synchronize_session=False
        )
        db.commit()
        print(f"Sucesso! {qtd} publicações com erro foram resetadas para PENDENTE.")
    except Exception as e:
        db.rollback()
        print(f"Erro ao resetar: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    resetar_erros()