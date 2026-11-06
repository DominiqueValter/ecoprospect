import re
import unicodedata
from datetime import datetime
from sqlalchemy.orm import Session
from app.database.connection import SessionLocal
from app.models.publicacao import PublicacaoBruta
from app.models.empresa import Empresa
from app.models.licenca import Licenca

# Palavras que indicam atos administrativos internos do IAT (não são licenças de empresas)
ATOS_INTERNOS_IGNORAR = [
    r"EDITAL DE NOTIFICAÇÃO",
    r"EDITAL TC",
    r"DESIGNA SUBSTITUT",
    r"DESIGNA GESTOR",
    r"PORTARIA N[º°]?\s*\d+.+DESIGNA",
    r"INSTRUÇÃO NORMATIVA",
    r"PARECER"
]

def normalizar_texto(texto: str) -> str:
    """Remove acentos, caracteres especiais e espaços extras para buscas padronizadas."""
    if not texto:
        return ""
    txt = unicodedata.normalize('NFD', texto)
    txt = "".join(c for c in txt if unicodedata.category(c) != 'Mn')
    txt = re.sub(r"[^A-Z0-9 ]", " ", txt.upper())
    return " ".join(txt.split())


def extrair_campo(padrao: str, texto: str) -> str:
    m = re.search(padrao, texto, re.I)
    return m.group(1).strip(" ,.-") if m else ""


def parse_sumula(texto: str, titulo: str):
    """Extrai campos estruturados do texto integral da súmula ou portaria."""
    
    # 1. Identificar se é ato interno a ignorar
    for pat in ATOS_INTERNOS_IGNORAR:
        if re.search(pat, titulo, re.I) or re.search(pat, texto, re.I):
            return None

    # 2. Extração de Razão Social / Empresa
    empresa = extrair_campo(
        r"torna p[úu]blico que\s+(?:concedeu|emitiu|autorizou|renovou|indeferiu|cancelou)?\s*(?:à|a|ao|às|aos)\s+(.+?),\s*(?:a|o|as|os|\d|Licen|Autoriza|LAS|LO|LP|LI|RLO|Prorroga)", 
        texto
    )
    if not empresa:
        # Padrão de Outorga de Recursos Hídricos
        empresa = extrair_campo(r"Outorgado\(s\)\s+(.+?)\s*-\s*(?:CPF/CNPJ|CPF|CNPJ)", texto)

    if not empresa or "INSTITUTO ÁGUA E TERRA" in empresa.upper():
        # Se não capturou empresa válida, descarta
        return None

    # 3. Extração de CNPJ / CPF (quando presente no texto)
    cnpj_match = re.search(r"\b(?:CNPJ|CPF|CPF/CNPJ)[\s:]*([\d.*\-/\s]+?\d{2,4})\b", texto, re.I)
    cnpj = cnpj_match.group(1).strip() if cnpj_match else None
    if not cnpj:
        cnpj_direct = re.search(r"\b(\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}|\d{3}\.\*\*\*\.\*\*\*-\d{2})\b", texto)
        cnpj = cnpj_direct.group(1) if cnpj_direct else None

    # 4. Tipo da Súmula e Tipo de Licença
    tipo_sumula = extrair_campo(r"(S[ÚU]MULA\s+DE\s+[^.\n]+?)(?=\s+O\s+Instituto|\s+torna|\,|$)", texto)
    if not tipo_sumula:
        tipo_sumula = extrair_campo(r"(S[ÚU]MULA\s+DE\s+[^\n.,]+)", texto)[:250]

    sigla_match = re.search(r"\b([A-Z]{2,5}(?:-[A-Z]{1,3})?)\s*n\.?\s*[º°o]\.?\s*(\d[\w\-./]*)", texto)
    if sigla_match:
        tipo_licenca = sigla_match.group(1).upper()
        numero_licenca = f"{sigla_match.group(1)} {sigla_match.group(2).rstrip('.,')}"
    else:
        tipo_licenca = "OUTORGA" if "OUTORGA" in titulo.upper() or "Portaria" in texto else "LICENÇA"
        num_port = re.search(r"Portaria\s+n[°°]?\s*([\d/\w\-]+)", texto, re.I)
        numero_licenca = f"PORTARIA {num_port.group(1)}" if num_port else "S/N"

    # 5. Validade
    validade_str = extrair_campo(r"validade\s+(?:at[ée]|de)\s+(\d{2}/\d{2}/\d{4}|\d+\s+anos)", texto)
    validade = None
    if validade_str and "/" in validade_str:
        try:
            validade = datetime.strptime(validade_str, "%d/%m/%Y").date()
        except ValueError:
            pass

    # 6. Atividade
    atividade = extrair_campo(
        r"validade\s+(?:at[ée]\s+\d{2}/\d{2}/\d{4}|\d+\s+anos),?\s+para\s+(.+?)\s+"
        r"(?:a\s+ser\s+)?(?:instalad[ao]|implantad[ao]|localizad[ao]|situad[ao])\b", 
        texto
    )
    if not atividade:
        atividade = extrair_campo(r"Finalidade\s+(.+?)(?:\.|\n|Vaz[ãa]o|$)", texto)

    # 7. Endereço
    endereco = extrair_campo(
        r"(?:instalad[ao]|implantad[ao]|localizad[ao]|situad[ao])\s+(?:na|no|em|à|ao|nas|nos)\s+"
        r"(.+?)\s+no\s+munic[íi]pio", 
        texto
    )

    # 8. Município e UF
    mun_match = re.search(r"munic[íi]pio\s+de\s+([^/.,\n]+?)(?:\s*/\s*([A-Z]{2})|\b|\.)", texto, re.I)
    if mun_match:
        municipio = mun_match.group(1).strip()
        uf = mun_match.group(2).upper() if mun_match.group(2) else "PR"
    else:
        mun2 = re.search(r"Munic[íi]pio\s+([^/.,\n]+?)(?:\.|\n|$)", texto, re.I)
        municipio = mun2.group(1).strip() if mun2 else "NÃO INFORMADO"
        uf = "PR"

    # 9. Protocolo
    prot_match = re.search(r"(?:protocolo|Prot\.)\s*n?[º°o]?\s*(\d[\w./\-]*)", texto, re.I)
    protocolo = prot_match.group(1).strip() if prot_match else ""

    return {
        "empresa": empresa,
        "cnpj": cnpj,
        "tipo_sumula": tipo_sumula,
        "tipo_licenca": tipo_licenca,
        "numero_licenca": numero_licenca,
        "validade": validade,
        "atividade": atividade,
        "endereco": endereco,
        "municipio": municipio,
        "uf": uf,
        "protocolo": protocolo
    }


def processar_publicacoes_pendentes(limite=500):
    db: Session = SessionLocal()
    try:
        pendentes = db.query(PublicacaoBruta).filter(
            PublicacaoBruta.processado == False
        ).limit(limite).all()

        if not pendentes:
            print("Nenhuma publicação pendente para processar.")
            return 0

        print(f"Processando {len(pendentes)} publicação(ões) pendente(s)...")
        processadas_com_sucesso = 0
        ignoradas_internas = 0

        for pub in pendentes:
            dados = parse_sumula(pub.texto_integral, pub.titulo_sumario)
            
            if not dados:
                # Ato interno ou matéria sem empresa (marca como processado para não travar)
                pub.processado = True
                ignoradas_internas += 1
                continue

            razao_social = dados["empresa"]
            municipio = dados["municipio"]
            razao_norm = normalizar_texto(razao_social)
            mun_norm = normalizar_texto(municipio)

            # Deduplicação inteligente de Empresa
            empresa = db.query(Empresa).filter(
                Empresa.razao_social_normalizada == razao_norm,
                Empresa.municipio == mun_norm
            ).first()

            if not empresa:
                empresa = Empresa(
                    razao_social=razao_social,
                    razao_social_normalizada=razao_norm,
                    cnpj=dados["cnpj"],
                    municipio=mun_norm,
                    uf=dados["uf"],
                    endereco_padrao=dados["endereco"]
                )
                db.add(empresa)
                db.flush()
            elif dados["cnpj"] and not empresa.cnpj:
                # Se encontrou CNPJ nesta publicação, atualiza o cadastro existente da empresa
                empresa.cnpj = dados["cnpj"]

            # Cadastro da Licença Consolidada
            licenca = Licenca(
                empresa_id=empresa.id,
                publicacao_origem_id=pub.id,
                protocolo=dados["protocolo"],
                tipo_sumula=dados["tipo_sumula"],
                tipo_licenca=dados["tipo_licenca"],
                numero_licenca=dados["numero_licenca"],
                validade=dados["validade"],
                atividade=dados["atividade"],
                endereco_empreendimento=dados["endereco"],
                municipio=mun_norm,
                uf=dados["uf"]
            )
            db.add(licenca)
            
            pub.processado = True
            processadas_com_sucesso += 1

        db.commit()
        print(f"Sucesso! {processadas_com_sucesso} licenças/empresas salvas | {ignoradas_internas} matérias internas ignoradas.")
        return processadas_com_sucesso

    except Exception as e:
        db.rollback()
        print(f"Erro durante o processamento do Bloco 2: {e}")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    processar_publicacoes_pendentes()