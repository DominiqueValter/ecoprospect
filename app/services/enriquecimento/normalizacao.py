"""Normalização de nomes para comparar a razão social da publicação com a base da Receita."""
import re
import unicodedata

# Sufixos/formas jurídicas ignorados na comparação "raiz"
SUFIXOS_JURIDICOS = {
    "LTDA", "LIMITADA", "ME", "EPP", "EIRELI", "SA", "S", "A", "SPE", "SLU",
    "MEI", "CIA", "COMPANHIA", "SOCIEDADE", "EMPRESARIA", "UNIPESSOAL",
}


def sem_acento(texto: str) -> str:
    nfkd = unicodedata.normalize("NFKD", texto or "")
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def normalizar(texto: str) -> str:
    """Maiúsculas, sem acento e sem pontuação: 'Zellamóveis - Compra Ltda.' -> 'ZELLAMOVEIS COMPRA LTDA'."""
    limpo = re.sub(r"[^A-Z0-9 ]", " ", sem_acento(texto).upper())
    return " ".join(limpo.split())


def raiz(texto: str) -> str:
    """
    Normalizado sem formas jurídicas e sem CPF/números finais (razão social de MEI
    é 'NOME DA PESSOA 12345678901'). 'PFD LOTEAMENTOS E INCORPORACOES LTDA' ->
    'PFD LOTEAMENTOS E INCORPORACOES'.
    """
    tokens = normalizar(texto).split()
    while tokens and (tokens[-1] in SUFIXOS_JURIDICOS or tokens[-1].isdigit()):
        tokens.pop()
    return " ".join(tokens)
