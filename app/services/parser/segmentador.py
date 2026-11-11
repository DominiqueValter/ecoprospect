import re

def segmentar_publicacao_em_atos(texto_integral: str) -> list[str]:
    """
    Recebe o texto bruto da matéria do DIOE e divide em blocos de atos independentes.
    Identifica demarcadores como 'O Instituto Água e Terra torna público...', 'SÚMULA DE...', 'EDITAL...'.
    """
    if not texto_integral:
        return []

    # Padroniza quebras de linha
    texto_limpo = texto_integral.replace("\r\n", "\n").strip()
    
    # Expressão de divisão nos marcadores conhecidos do IAT / DIOE
    padrao_separacao = r"(?=(?:O\s+Instituto\s+Água\s+e\s+Terra\s+torna\s+público|SÚMULA\s+DE|SUMULA\s+DE|EDITAL\s+DE|PORTARIA\s+N[º°]?))"
    
    blocos_brutos = re.split(padrao_separacao, texto_limpo, flags=re.IGNORECASE)
    
    atos_segmentados = []
    for bloco in blocos_brutos:
        bloco_fmt = bloco.strip()
        # Filtra blocos vazios ou linhas muito curtas sem relevância
        if len(bloco_fmt) > 30:
            atos_segmentados.append(bloco_fmt)
            
    return atos_segmentados