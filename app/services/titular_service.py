import re

# Indicadores explícitos de Pessoa Jurídica
PALAVRAS_CHAVE_PJ = [
    r"\bLTDA\b", r"\bS/?A\b", r"\bSPE\b", r"\bME\b", r"\bEPP\b",
    r"\bCOOPERATIVA\b", r"\bCOMPANHIA\b", r"\bCIA\b", r"\bINDUSTRIA\b",
    r"\bCOMERCIO\b", r"\bSERVICOS\b", r"\bEMPREENDIMENTOS\b", r"\bAGROPECUARIA\b",
    r"\bCONSTRUTORA\b", r"\bPOSTO\b", r"\bMINERACAO\b", r"\bPOSTOS\b",
    r"\bDISTRIBUIDORA\b", r"\bFABRICA\b", r"\bAUTO\b", r"\bLAVA\s+CAR\b"
]

# Indicadores explícitos de Órgãos Públicos
PALAVRAS_CHAVE_ORGAO = [
    r"\bPREFEITURA\b", r"\bSECRETARIA\b", r"\bMUNICIPIO\s+DE\b",
    r"\bDEPARTAMENTO\b", r"\bSANEPAR\b", r"\bCOPEL\b", r"\bDER/PR\b",
    r"\bINSTITUTO\s+AGUA\s+E\s+TERRA\b", r"\bIAT\b", r"\bGOVERNO\b"
]


def validar_cpf(cpf_str: str) -> bool:
    """Valida o formato e os dígitos verificadores do CPF."""
    digits = [int(c) for c in re.sub(r"\D", "", str(cpf_str or ""))]
    if len(digits) != 11 or len(set(digits)) == 1:
        return False
    
    # Primeiro dígito verificador
    soma = sum(a * b for a, b in zip(digits[:9], range(10, 1, -1)))
    d1 = (soma * 10 % 11) % 10
    if digits[9] != d1:
        return False

    # Segundo dígito verificador
    soma = sum(a * b for a, b in zip(digits[:10], range(11, 1, -1)))
    d2 = (soma * 10 % 11) % 10
    return digits[10] == d2


def validar_cnpj(cnpj_str: str) -> bool:
    """Valida o formato e os dígitos verificadores do CNPJ."""
    digits = [int(c) for c in re.sub(r"\D", "", str(cnpj_str or ""))]
    if len(digits) != 14 or len(set(digits)) == 1:
        return False

    def calc_digito(nums, pesos):
        soma = sum(a * b for a, b in zip(nums, pesos))
        resto = soma % 11
        return 0 if resto < 2 else 11 - resto

    d1 = calc_digito(digits[:12], [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2])
    d2 = calc_digito(digits[:13], [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2])
    return digits[12] == d1 and digits[13] == d2


def identificar_tipo_titular(nome_titular: str, doc_str: str = None) -> tuple[str, str, str, str]:
    """
    Classifica o titular em PJ, PF, ORGAO_PUBLICO ou INDETERMINADO.
    Retorna: (tipo_titular, cnpj_validado, cpf_validado, elegibilidade_b2b)
    """
    nome_upper = (nome_titular or "").upper().strip()
    doc_limpo = re.sub(r"\D", "", doc_str or "")

    cnpj = None
    cpf = None

    # Check 1: Validação por documento (se fornecido)
    if len(doc_limpo) == 14:
        if validar_cnpj(doc_limpo):
            cnpj = doc_limpo
            return "PJ", cnpj, None, "ELEGIVEL"
    elif len(doc_limpo) == 11:
        if validar_cpf(doc_limpo):
            cpf = doc_limpo
            return "PF", None, cpf, "PF_IGNORADA_B2B"

    # Check 2: Verificação de Órgão Público
    for pat in PALAVRAS_CHAVE_ORGAO:
        if re.search(pat, nome_upper):
            return "ORGAO_PUBLICO", None, None, "ORGAO_IGNORADO"

    # Check 3: Verificação de Palavras-Chave de Pessoa Jurídica
    for pat in PALAVRAS_CHAVE_PJ:
        if re.search(pat, nome_upper):
            return "PJ", cnpj, None, "ELEGIVEL"

    # Check 4: Análise Heurística de Nomes Próprios (Pessoa Física)
    partes_nome = nome_upper.split()
    if 2 <= len(partes_nome) <= 5 and not any(char.isdigit() for char in nome_upper):
        # Ex: "MARIA CRISTINA MICHALSKI", "CLAUDIR VISSOTO"
        return "PF", None, cpf, "PF_IGNORADA_B2B"

    # Se não houver clareza técnica
    return "INDETERMINADO", None, None, "REVISAO_MANUAL"