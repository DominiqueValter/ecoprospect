from datetime import date, timedelta
from sqlalchemy.orm import Session
from app.database.connection import SessionLocal
from app.models.licenca import Licenca
from app.models.empresa import Empresa


def calcular_situacao_renovacao(validade: date, hoje: date = None) -> tuple[int, date, str]:
    if not validade:
        return None, None, "SEM_VALIDADE"
    
    hoje = hoje or date.today()
    dias_para_vencer = (validade - hoje).days
    limite_120d = validade - timedelta(days=120)

    if validade < hoje:
        situacao = "EXPIRADA"
    elif limite_120d < hoje:
        situacao = "PRAZO_120D_PASSOU"
    else:
        situacao = "DENTRO_PRAZO_120D"

    return dias_para_vencer, limite_120d, situacao


def processar_controle_validade(hoje: date = None):
    db: Session = SessionLocal()
    hoje = hoje or date.today()
    print(f"Calculando controle de validade e vencimentos para a data base: {hoje:%d/%m/%Y}...")

    try:
        licencas = db.query(Licenca).all()
        if not licencas:
            print("Nenhuma licença cadastrada para processar.")
            return 0

        # Mapeamento para detecção de renovações posteriores
        licencas_por_empresa = {}
        for l in licencas:
            chave = (l.empresa_id, l.atividade)
            licencas_por_empresa.setdefault(chave, []).append(l)

        atualizadas = 0

        for lic in licencas:
            if not lic.validade:
                continue

            dias, limite_120d, situacao = calcular_situacao_renovacao(lic.validade, hoje)
            
            lic.dias_para_vencer = dias
            lic.limite_renovacao_120d = limite_120d
            lic.situacao_renovacao = situacao

            # Detecção de publicação posterior (Renovação já realizada no IAT)
            chave = (lic.empresa_id, lic.atividade)
            posteriores = [
                o for o in licencas_por_empresa.get(chave, [])
                if o.id != lic.id 
                and o.validade 
                and o.validade > lic.validade
            ]

            if posteriores:
                lic.renovacao_publicada_posterior = "; ".join(
                    f"{o.numero_licenca} válida até {o.validade:%d/%m/%Y}"
                    for o in sorted(posteriores, key=lambda x: x.validade, reverse=True)
                )
            else:
                lic.renovacao_publicada_posterior = None

            atualizadas += 1

        db.commit()
        print(f"Sucesso! {atualizadas} licenças com regras de vencimento e 120 dias calculadas.")
        return atualizadas

    except Exception as e:
        db.rollback()
        print(f"Erro ao processar controle de validade: {e}")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    processar_controle_validade()