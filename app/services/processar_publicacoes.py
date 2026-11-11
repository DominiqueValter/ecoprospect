from datetime import datetime
from sqlalchemy.orm import Session
from app.database.connection import SessionLocal
from app.models.publicacao import PublicacaoBruta
from app.services.parser.segmentador import segmentar_publicacao_em_atos
from app.services.parser.extrator_atos import extrair_dados_do_ato
from app.services.empresa_service import resolver_titular
from app.services.licenca_service import resolver_licenca

def processar_publicacoes_pendentes(limite: int = 100):
    db: Session = SessionLocal()
    print("Iniciando orquestração de processamento com gestão de estados...")

    try:
        # Busca matérias que ainda estão pendentes
        publicacoes = db.query(PublicacaoBruta).filter(
            PublicacaoBruta.status_processamento == "PENDENTE"
        ).limit(limite).all()

        if not publicacoes:
            print("Nenhuma publicação pendente encontrada.")
            return 0

        processadas = 0
        revisoes = 0
        erros = 0

        for pub in publicacoes:
            try:
                # 1. Segmenta o texto integral em atos individuais
                atos_textos = segmentar_publicacao_em_atos(pub.texto_integral)
                
                if not atos_textos:
                    pub.status_processamento = "REVISAO_MANUAL"
                    pub.motivo_revisao = "Nenhum ato ambiental reconhecido na publicação."
                    revisoes += 1
                    continue

                atos_processados_com_sucesso = 0
                precisa_revisao = False
                motivos_rev = []

                for ato_txt in atos_textos:
                    dados_ato = extrair_dados_do_ato(ato_txt, pub.titulo_sumario or "")
                    if not dados_ato:
                        continue

                    # 2. Resolve o Titular (PF, PJ ou Órgão Público)
                    empresa, res_titular = resolver_titular(db, dados_ato)
                    if not empresa:
                        precisa_revisao = True
                        motivos_rev.append("Não foi possível identificar o titular com segurança.")
                        continue

                    # 3. Resolve a Licença/Ato Ambiental
                    licenca, foi_criada = resolver_licenca(db, empresa.id, pub.id, dados_ato)
                    atos_processados_com_sucesso += 1

                    if dados_ato.get("situacao_validacao") == "REVISAO_MANUAL":
                        precisa_revisao = True
                        motivos_rev.append(dados_ato.get("motivo_revisao_manual") or "Validação incompleta.")

                # 4. Atualiza o estado da Publicação Bruta
                pub.processado = True
                pub.processado_em = datetime.utcnow()

                if precisa_revisao:
                    pub.status_processamento = "REVISAO_MANUAL"
                    pub.motivo_revisao = "; ".join(set(motivos_rev))
                    revisoes += 1
                elif atos_processados_com_sucesso > 0:
                    pub.status_processamento = "PROCESSADA"
                    pub.motivo_revisao = None
                    processadas += 1
                else:
                    pub.status_processamento = "REVISAO_MANUAL"
                    pub.motivo_revisao = "Matéria não continha licenças ambientais válidas."
                    revisoes += 1

            except Exception as e:
                pub.status_processamento = "ERRO"
                pub.motivo_revisao = f"Exceção no processamento: {str(e)}"
                erros += 1

        db.commit()
        print(f"Sucesso! Processadas: {processadas} | Revisão Manual: {revisoes} | Erros: {erros}")
        return processadas

    except Exception as e:
        db.rollback()
        print(f"Erro geral no orquestrador: {e}")
        return 0
    finally:
        db.close()

if __name__ == "__main__":
    processar_publicacoes_pendentes()