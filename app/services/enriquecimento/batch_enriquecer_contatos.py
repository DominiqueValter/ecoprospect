import time
import json
import urllib.request
import urllib.error
from sqlalchemy.orm import Session
from sqlalchemy import Table, MetaData
from app.database.connection import SessionLocal, engine
from app.models.empresa import Empresa

# Refletir as tabelas do banco de dados dinamicamente para evitar ImportError
metadata = MetaData()

try:
    from app.models.empresa_enriquecida import EmpresaEnriquecida
except Exception:
    # Se a classe ORM não for encontrada por import, reflete direto do banco
    class EmpresaEnriquecida:
        pass
    table_enriquecida = Table('empresas_enriquecidas', metadata, autoload_with=engine)
    from sqlalchemy.orm import mapper
    # Para SQLAlchemy 2.0+ / 1.4+
    from sqlalchemy.orm import registry
    mapper_registry = registry()
    mapper_registry.map_imperatively(EmpresaEnriquecida, table_enriquecida)

try:
    from app.models.contato import ContatoEmpresa
except Exception:
    class ContatoEmpresa:
        pass
    table_contatos = Table('contatos_empresa', metadata, autoload_with=engine)
    from sqlalchemy.orm import registry
    mapper_registry = registry()
    mapper_registry.map_imperatively(ContatoEmpresa, table_contatos)

API_BRASIL_URL = "https://brasilapi.com.br/api/cnpj/v1/{cnpj}"

def limpar_cnpj(cnpj_raw: str) -> str:
    if not cnpj_raw:
        return ""
    return "".join(filter(str.isdigit, str(cnpj_raw))).zfill(14)

def buscar_dados_cnpj_brasilapi(cnpj: str):
    """Consulta dados cadastrais na BrasilAPI usando urllib (nativo)."""
    cnpj_limpo = limpar_cnpj(cnpj)
    if not cnpj_limpo or len(cnpj_limpo) != 14:
        return None
    
    url = API_BRASIL_URL.format(cnpj=cnpj_limpo)
    req = urllib.request.Request(
        url, 
        headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            if response.status == 200:
                data = response.read().decode('utf-8')
                return json.loads(data)
    except urllib.error.HTTPError as e:
        print(f"⚠️ HTTP {e.code} ao consultar CNPJ {cnpj_limpo}")
    except Exception as e:
        print(f"❌ Erro ao consultar CNPJ {cnpj_limpo}: {e}")
    return None

def processar_batch_enriquecimento():
    db: Session = SessionLocal()
    try:
        # 1. Buscar empresas pendentes em empresas_enriquecidas
        pendentes = db.query(EmpresaEnriquecida).filter(
            EmpresaEnriquecida.status_enriquecimento == "PENDENTE"
        ).all()

        print(f"🔍 Encontradas {len(pendentes)} empresas pendentes de enriquecimento.")

        for item in pendentes:
            empresa_pai = db.query(Empresa).filter(Empresa.id == item.empresa_id).first()
            if not empresa_pai:
                continue

            cnpj_alvo = item.cnpj_limpo or empresa_pai.cnpj

            # Se a empresa não possui CNPJ gravado
            if not cnpj_alvo:
                print(f"⚠️ Empresa ID {empresa_pai.id} ({empresa_pai.razao_social}) não possui CNPJ gravado. Marcando para revisão manual...")
                item.motivo_estado = "CNPJ_NAO_ENCONTRADO"
                item.status_enriquecimento = "REVISAO_MANUAL"
                db.commit()
                continue

            cnpj_limpo = limpar_cnpj(cnpj_alvo)
            print(f"🔄 Processando CNPJ: {cnpj_limpo} | Empresa: {empresa_pai.razao_social}")

            dados = buscar_dados_cnpj_brasilapi(cnpj_limpo)
            if not dados:
                item.status_enriquecimento = "ERRO"
                item.motivo_estado = "FALHA_CONSULTA_API"
                db.commit()
                continue

            # 2. Atualizar tabela empresas_enriquecidas
            item.cnpj_limpo = cnpj_limpo
            item.razao_social_oficial = dados.get("razao_social") or empresa_pai.razao_social
            item.nome_fantasia = dados.get("nome_fantasia")
            item.situacao_cadastral = dados.get("descricao_situacao_cadastral")
            item.cnae_principal_codigo = str(dados.get("cnae_fiscal", ""))
            item.cnae_principal_descricao = dados.get("cnae_fiscal_descricao")
            item.porte = dados.get("porte")
            item.logradouro = dados.get("logradouro")
            item.numero = dados.get("numero")
            item.bairro = dados.get("bairro")
            item.cep = dados.get("cep")
            item.status_enriquecimento = "CONCLUIDO"
            item.motivo_estado = None

            # 3. Salvar contatos na tabela contatos_empresa
            contatos_adicionados = 0

            # E-mail
            email = dados.get("email")
            if email and email.strip():
                db.add(ContatoEmpresa(
                    empresa_id=empresa_pai.id,
                    tipo_contato="EMAIL",
                    valor=email.lower().strip(),
                    origem="RECEITA_FEDERAL",
                    principal=True
                ))
                contatos_adicionados += 1

            # Telefones
            tel1 = dados.get("ddd_telefone_1") or dados.get("telefone1")
            tel2 = dados.get("ddd_telefone_2") or dados.get("telefone2")

            for idx, tel in enumerate([tel1, tel2]):
                if tel and str(tel).strip():
                    db.add(ContatoEmpresa(
                        empresa_id=empresa_pai.id,
                        tipo_contato="TELEFONE",
                        valor=str(tel).strip(),
                        origem="RECEITA_FEDERAL",
                        principal=(idx == 0)
                    ))
                    contatos_adicionados += 1

            # Quadro de Sócios e Administradores (QSA)
            qsa = dados.get("qsa", [])
            for socio in qsa:
                nome_socio = socio.get("nome_socio_razao_social") or socio.get("nome")
                cargo = socio.get("qualificacao_socio") or socio.get("qualificacao")
                if nome_socio:
                    db.add(ContatoEmpresa(
                        empresa_id=empresa_pai.id,
                        tipo_contato="SOCIO_ADMINISTRADOR",
                        valor=f"{nome_socio} ({cargo})" if cargo else nome_socio,
                        origem="QSA_RECEITA",
                        principal=False
                    ))
                    contatos_adicionados += 1

            db.commit()
            print(f"✅ Sucesso! {contatos_adicionados} contatos gravados para {empresa_pai.razao_social}.")

            # Respeitar rate limit da API gratuita (1.5 segundos entre requisições)
            time.sleep(1.5)

    except Exception as e:
        db.rollback()
        print(f"❌ Erro geral no batch: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    processar_batch_enriquecimento()