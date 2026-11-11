from app.services.parser.segmentador import segmentar_publicacao_em_atos
from app.services.parser.extrator_atos import extrair_dados_do_ato

# Texto real enviado por você contendo os 3 atos na mesma matéria do DIOE
TEXTO_EXEMPLO_DIOE = """
O Instituto Água e Terra torna público que concedeu à ZELLAMÓVEIS - COMPRA E VENDA DE IMÓVEIS LTDA, a Autorização Ambiental - AA nº 65643 com validade até 03/11/2028, para Levantamento de Fauna a ser implantada na Rua Antônio Mioto, 800 no município de Paranaguá/PR.

O Instituto Água e Terra torna público que concedeu à C.VALE - COOPERATIVA AGROINDUSTRIAL, a Licença de Operação - LO nº 389522 com validade até 03/11/2028, para Comércio e Serviço - Armazenadoras de Produtos Agrotóxicos, seus componentes e afins instalada na Lote rural n°52-53, Gleba 05, sn no município de São Pedro do Iguaçu/PR.  

O Instituto Água e Terra torna público que concedeu à DISTRIBUIDORA DE INSUMOS LUGARINI LTDA, a Licença Prévia - LP nº 389805 com validade até 03/11/2028, para Industrial - Beneficiamento e armazenamento de produtos agrícolas a ser implantada na ESTRADA DO CERNE PR 090, 10215 no município de Campo Magro/PR.
"""

def testar_exemplos():
    print("=== TESTANDO ETAPA 2 NOS 3 EXEMPLOS REAIS DO DIOE ===")
    
    # 1. Segmentação
    atos = segmentar_publicacao_em_atos(TEXTO_EXEMPLO_DIOE)
    print(f"\n[+] Total de Atos Segmentados: {len(atos)} (Esperado: 3)")
    
    for idx, ato_texto in enumerate(atos, start=1):
        print(f"\n--- ATO #{idx} ---")
        dados = extrair_dados_do_ato(ato_texto)
        if dados:
            print(f"Titular:       {dados['titular']}")
            print(f"Tipo Titular:  {dados['tipo_titular']} | Elegibilidade B2B: {dados['elegibilidade_b2b']}")
            print(f"Documento:     {dados['tipo_licenca']} nº {dados['numero_licenca']}")
            print(f"Validade:      {dados['validade']}")
            print(f"Atividade:     {dados['atividade']}")
            print(f"Endereço:      {dados['endereco']}")
            print(f"Município:     {dados['municipio']}/{dados['uf']}")
        else:
            print("Erro ao extrair dados do ato!")

if __name__ == "__main__":
    testar_exemplos()