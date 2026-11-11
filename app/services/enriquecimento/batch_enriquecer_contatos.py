"""
Batch de enriquecimento: processa as empresas pendentes.

A versão anterior importava módulos inexistentes (app.models.empresa_enriquecida,
app.models.contato), gravava campos que o modelo não tem (origem, principal) e
usava estados diferentes (CONCLUIDO/ERRO) dos do modelo. Agora é só um atalho
para o agente em app/services/enriquecimento_contatos.py.

Uso:
  python -m app.services.enriquecimento.batch_enriquecer_contatos [--limite N] [--reprocessar]
"""
from app.services.enriquecimento_contatos import main

if __name__ == "__main__":
    main()
