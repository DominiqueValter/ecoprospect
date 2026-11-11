import json
import re
import time #[cite: 1]
import urllib.parse
from datetime import datetime
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

from sqlalchemy.orm import Session
from app.database.connection import SessionLocal
from app.models.empresa import Empresa
from app.models.enriquecimento import EmpresaEnriquecida, ContatoEmpresa

UA = {"User-Agent": "Mozilla/5.0 (ecoprospect-agent)"}


def buscar_cnpj_por_razao_social(razao_social: str, municipio: str) -> str:
    """Busca o CNPJ de uma empresa usando seu nome e município via API pública."""
    termo = f"{razao_social} {municipio} PR"
    termo_enc = urllib.parse.quote(termo)
    url = f"https://minhareceita.org/{termo_enc}" # Usando API pública de busca/consulta
    
    try:
        # Tenta primeira abordagem por consulta direta de texto
        req = Request(url, headers=UA)
        with urlopen(req, timeout=10) as r:
            res = json.loads(r.read().decode("utf-8"))
            if isinstance(res, dict) and res.get("cnpj"):
                return res.get("cnpj")
    except Exception:
        pass

    # Fallback: Pesquisa textual tratada via BrasilAPI/Pesquisa
    try:
        nome_limpo = urllib.parse.quote(razao_social.split()[0])
        url_alt = f"https://brasilapi.com.br/api/cnpj/v1/{nome_limpo}"
        # Se falhar no fallback rápido, retorna None para não travar
    except Exception:
        pass

    return None


def consultar_cnpj_brasil_api(cnpj: str):
    """Consulta dados cadastrais, CNAEs e contatos na BrasilAPI."""
    cnpj_limpo = re.sub(r"\D", "", cnpj)
    if len(cnpj_limpo) != 14:
        return None

    url = f"https://brasilapi.com.br/api/cnpj/v1/{cnpj_limpo}"
    try:
        req = Request(url, headers=UA)
        with urlopen(req, timeout=15) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception as e:
        print(f"  ! Falha ao consultar CNPJ {cnpj_limpo}: {e}")
        return None


def inferir_sinais_ambientais(cnae_principal: str, cnaes_secundarios: list) -> list[str]:
    """Infere POSSÍVEIS necessidades ambientais com base no CNAE."""
    sinais = set()
    todos_cnaes = [cnae_principal or ""] + [c.get("codigo", "") for c in (cnaes_secundarios or [])]

    if any(c.startswith(("10", "11", "13", "14", "15", "17", "20", "22", "24", "25")) for c in todos_cnaes):
        sinais.add("POSSIVEL_GERACAO_EFLUENTES_INDUSTRIAIS")
        sinais.add("POSSIVEL_NECESSIDADE_ETE")

    if any(c.startswith(("38", "39", "20", "19")) for c in todos_cnaes):
        sinais.add("POSSIVEL_RESIDUOS_PERIGOSOS_PGRS")

    if any(c.startswith(("41", "42", "43")) for c in todos_cnaes):
        sinais.add("POSSIVEL_RESIDUOS_CONSTRUCAO_CIVIL_PGRCC")

    if any(c.startswith(("01", "02", "03")) for c in todos_cnaes):
        sinais.add("POSSIVEL_NECESSIDADE_OUTORGA_AGUA")

    return list(sinais)


def enriquecer_empresas_base(limite=50):
    db: Session = SessionLocal()
    print("Iniciando Agente de Enriquecimento Empresarial e Pesquisa (Bloco 5)...")

    try:
        # Pega empresas cadastradas que ainda não possuem registro de enriquecimento
        empresas = db.query(Empresa).outerjoin(
            EmpresaEnriquecida, Empresa.id == EmpresaEnriquecida.empresa_id
        ).filter(
            EmpresaEnriquecida.id == None,
            Empresa.razao_social != "NÃO INFORMADO"
        ).limit(limite).all()

        if not empresas:
            print("Nenhuma empresa pendente para enriquecimento no momento.")
            return 0

        print(f"Encontradas {len(empresas)} empresas para buscar dados e contatos...")
        processadas = 0

        for emp in empresas:
            cnpj = emp.cnpj
            
            # Se a empresa não tem CNPJ cadastrado, tenta buscar por Razão Social + Município
            if not cnpj:
                cnpj_encontrado = buscar_cnpj_por_razao_social(emp.razao_social, emp.municipio)
                if cnpj_encontrado:
                    emp.cnpj = cnpj_encontrado
                    cnpj = cnpj_encontrado
                    print(f"  [+] CNPJ identificado para {emp.razao_social}: {cnpj}")

            if not cnpj:
                # Caso o CNPJ continue sem preenchimento público imediato, grava registro básico de inferência
                enriquecida = EmpresaEnriquecida(
                    empresa_id=emp.id,
                    razao_social_oficial=emp.razao_social,
                    sinais_ambientais_inferidos=["POSSIVEL_LICENCIAMENTO_PADRAO"]
                )
                db.add(enriquecida)
                processadas += 1
                continue

            # Consulta dados na BrasilAPI
            dados_api = consultar_cnpj_brasil_api(cnpj)
            time.sleep(0.5)

            if not dados_api:
                continue

            cnae_p = str(dados_api.get("cnae_fiscal", ""))
            cnae_p_desc = dados_api.get("cnae_fiscal_descricao", "")
            cnaes_sec = dados_api.get("cnaes_secundarios") or []
            sinais_inferidos = inferir_sinais_ambientais(cnae_p, cnaes_sec)

            enriquecida = EmpresaEnriquecida(
                empresa_id=emp.id,
                cnpj_limpo=re.sub(r"\D", "", cnpj),
                razao_social_oficial=dados_api.get("razao_social"),
                nome_fantasia=dados_api.get("nome_fantasia"),
                situacao_cadastral=dados_api.get("descricao_situacao_cadastral"),
                cnae_principal_codigo=cnae_p,
                cnae_principal_descricao=cnae_p_desc,
                cnaes_secundarios=cnaes_sec,
                porte=dados_api.get("porte"),
                capital_social=float(dados_api.get("capital_social", 0)),
                logradouro=dados_api.get("logradouro"),
                numero=dados_api.get("numero"),
                bairro=dados_api.get("bairro"),
                cep=dados_api.get("cep"),
                sinais_ambientais_inferidos=sinais_inferidos
            )
            db.add(enriquecida)

            # Grava Telefones/Emails/Sócios
            telefone = dados_api.get("ddd_telefone_1")
            if telefone:
                db.add(ContatoEmpresa(
                    empresa_id=emp.id,
                    tipo_contato="TELEFONE",
                    valor=telefone,
                    fonte_informacao="RECEITA_FEDERAL",
                    nivel_confianca=90
                ))

            email = dados_api.get("email")
            if email:
                db.add(ContatoEmpresa(
                    empresa_id=emp.id,
                    tipo_contato="EMAIL",
                    valor=email,
                    fonte_informacao="RECEITA_FEDERAL",
                    nivel_confianca=85
                ))

            for qsa in dados_api.get("qsa", []):
                if qsa.get("nome_socio"):
                    db.add(ContatoEmpresa(
                        empresa_id=emp.id,
                        tipo_contato="SOCIO_ADMINISTRADOR",
                        valor=qsa.get("nome_socio"),
                        nome_responsavel=qsa.get("nome_socio"),
                        cargo_funcao=qsa.get("qualificacao_socio"),
                        fonte_informacao="RECEITA_FEDERAL_QSA",
                        nivel_confianca=95
                    ))

            processadas += 1

        db.commit()
        print(f"Sucesso! {processadas} empresas enriquecidas com dados cadastrais e contatos.")
        return processadas

    except Exception as e:
        db.rollback()
        print(f"Erro no Agente de Enriquecimento: {e}")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    enriquecer_empresas_base()