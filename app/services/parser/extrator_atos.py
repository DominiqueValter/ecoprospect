import re
import unicodedata
from datetime import datetime
from app.services.titular_service import identificar_tipo_titular


def normalizar_texto(texto: str) -> str:
    if not texto:
        return ""
    txt = unicodedata.normalize('NFD', texto)
    txt = "".join(c for c in txt if unicodedata.category(c) != 'Mn')
    txt = re.sub(r"[^A-Z0-9 ]", " ", txt.upper())
    return " ".join(txt.split())


def extrair_dados_do_ato(texto_ato: str, titulo_materia: str = "") -> dict | None:
    """
    Extrai com alta precisão os dados de UM ato ambiental individual.
    """
    if not texto_ato:
        return None

    # 1. Ignorar atos administrativos exclusivamente internos do IAT
    if re.search(r"(DESIGNA\s+SUBSTITUT|DESIGNA\s+GESTOR|EDITAL\s+DE\s+NOTIFICAÇÃO\s+DE\s+JULGAMENTO)", texto_ato, re.I):
        return None

    # 2. Extração da Titular / Razão Social
    titular = ""
    m_emp = re.search(
        r"torna p[úu]blico que\s+(?:concedeu|emitiu|autorizou|renovou|indeferiu|cancelou)?\s*(?:à|a|ao|às|aos)\s+(.+?),\s*(?:a|o|as|os|\d|Licen|Autoriza|LAS|LO|LP|LI|RLO|AA|LOR|Prorroga)",
        texto_ato, re.I
    )
    if m_emp:
        titular = m_emp.group(1).strip(" ,.-")
    else:
        m_out = re.search(r"Outorgado\(s\)\s+(.+?)\s*-\s*(?:CPF/CNPJ|CPF|CNPJ)", texto_ato, re.I)
        if m_out:
            titular = m_out.group(1).strip(" ,.-")

    if not titular or "INSTITUTO ÁGUA E TERRA" in titular.upper():
        return None

    # 3. Extração de Documento (CNPJ/CPF se houver no texto)
    doc_match = re.search(r"\b(?:CNPJ|CPF|CPF/CNPJ)[\s:]*([\d.*\-/\s]+?\d{2,4})\b", texto_ato, re.I)
    doc_str = doc_match.group(1).strip() if doc_match else None
    if not doc_str:
        doc_direct = re.search(r"\b(\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}|\d{3}\.\d{3}\.\d{3}-\d{2}|\d{3}\.\*\*\*\.\*\*\*-\d{2})\b", texto_ato)
        doc_str = doc_direct.group(1) if doc_direct else None

    # 4. Classificação do Tipo de Titular (PJ vs PF vs Orgão Público)
    tipo_titular, cnpj, cpf, elegibilidade_b2b = identificar_tipo_titular(titular, doc_str)

    # 5. Tipo da Súmula e Tipo de Licença (AA, LO, LP, LI, LAS, RLO, LOR, OUTORGA)
    tipo_licenca = "LICENÇA"
    numero_licenca = "S/N"
    
    sigla_match = re.search(r"\b(LAS-A|LO-A|LAS|RLO|LOR|AA|LO|LP|LI)\b\s*n[º°o]?\.?\s*(\d[\w\-./]*)", texto_ato, re.I)
    
    if sigla_match:
        tipo_licenca = sigla_match.group(1).upper()
        num_apenas = sigla_match.group(2).rstrip('.,')
        numero_licenca = f"{tipo_licenca} {num_apenas}"
    else:
        num_generic = re.search(r"n[º°o]\s*(\d[\w\-./]*)", texto_ato, re.I)
        num_apenas = num_generic.group(1).rstrip('.,') if num_generic else ""
        if "AUTORIZAÇÃO" in texto_ato.upper() or "AA" in texto_ato.upper():
            tipo_licenca = "AA"
        elif "OUTORGA" in texto_ato.upper() or "PORTARIA" in texto_ato.upper():
            tipo_licenca = "OUTORGA"
        numero_licenca = f"{tipo_licenca} {num_apenas}".strip() if num_apenas else f"{tipo_licenca} S/N"

    # 6. Validade (Data DD/MM/AAAA)
    validade = None
    val_match = re.search(r"validade\s+(?:at[ée]|de)\s+(\d{2}/\d{2}/\d{4})", texto_ato, re.I)
    if val_match:
        try:
            validade = datetime.strptime(val_match.group(1), "%d/%m/%Y").date()
        except ValueError:
            pass

    # 7. Atividade
    atividade = ""
    m_ativ = re.search(
        r"para\s+(.+?)\s+(?:a\s+ser\s+)?(?:instalad[ao]|implantad[ao]|localizad[ao]|situad[ao])",
        texto_ato, re.I
    )
    if m_ativ:
        atividade = m_ativ.group(1).strip(" ,.-")
    else:
        m_fin = re.search(r"Finalidade\s+(.+?)(?:\.|\n|Vaz[ãa]o|$)", texto_ato, re.I)
        if m_fin:
            atividade = m_fin.group(1).strip(" ,.-")

    # 8. Endereço do Empreendimento
    endereco = ""
    m_end = re.search(
        r"(?:instalad[ao]|implantad[ao]|localizad[ao]|situad[ao])\s+(?:na|no|em|à|ao|nas|nos)\s+(.+?)\s+no\s+munic[íi]pio",
        texto_ato, re.I
    )
    if m_end:
        endereco = m_end.group(1).strip(" ,.-")

    # 9. Município e UF
    municipio = "NÃO INFORMADO"
    uf = "PR"
    m_mun = re.search(r"munic[íi]pio\s+de\s+([A-Za-zÀ-ÖØ-öø-ÿ\s'-]+?)(?:\s*/\s*([A-Z]{2})|\s*\.|\s*,|\n|$)", texto_ato, re.I)
    if m_mun:
        municipio = m_mun.group(1).strip()
        uf = m_mun.group(2).upper() if m_mun.group(2) else "PR"
    else:
        m_mun2 = re.search(r"Munic[íi]pio\s+([A-Za-zÀ-ÖØ-öø-ÿ\s'-]+?)(?:\s*\.|\s*,|\n|$)", texto_ato, re.I)
        if m_mun2:
            municipio = m_mun2.group(1).strip()

    # 10. Protocolo
    prot_match = re.search(r"(?:protocolo|Prot\.)\s*n?[º°o]?\s*(\d[\w./\-]*)", texto_ato, re.I)
    protocolo = prot_match.group(1).strip() if prot_match else None

    # Nível de confiança da extração (0.0 a 1.0)
    confianca = 1.0
    situacao_validacao = "VALIDADO"
    motivo_revisao = None

    if municipio == "NÃO INFORMADO" or not atividade:
        confianca = 0.7
        situacao_validacao = "REVISAO_MANUAL"
        motivo_revisao = "Município ou Atividade não capturada com certeza técnica."

    return {
        "titular": titular,
        "tipo_titular": tipo_titular,
        "cnpj": cnpj,
        "cpf": cpf,
        "elegibilidade_b2b": elegibilidade_b2b,
        "tipo_licenca": tipo_licenca,
        "numero_licenca": numero_licenca,
        "validade": validade,
        "atividade": atividade,
        "endereco": endereco,
        "municipio": municipio,
        "uf": uf,
        "protocolo": protocolo,
        "snippet_evidencia": texto_ato[:1000],  # Salva o trecho exato para auditoria
        "nivel_confianca": confianca,
        "situacao_validacao": situacao_validacao,
        "motivo_revisao_manual": motivo_revisao
    }