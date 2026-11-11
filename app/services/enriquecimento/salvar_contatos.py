from app.database.connection import SessionLocal
from app.models.contato import ContatoEmpresa  # seu modelo de contatos

def salvar_contatos_extraidos(empresa_id: int, dados_api: dict):
    """
    Persiste os telefones, e-mails e pessoas de contato retornados pela API de CNPJ
    na tabela contatos_empresa.
    """
    db = SessionLocal()
    contatos_criados = 0
    try:
        # 1. Extrair e-mail principal
        email = dados_api.get("email")
        if email:
            contato_email = ContatoEmpresa(
                empresa_id=empresa_id,
                tipo_contato="EMAIL",
                valor=email.lower().strip(),
                origem="RECEITA_FEDERAL",
                principal=True
            )
            db.add(contato_email)
            contatos_criados += 1

        # 2. Extrair telefones (DDD + Número)
        telefones = [dados_api.get("telefone1"), dados_api.get("telefone2")]
        for idx, tel in enumerate(telefones):
            if tel:
                contato_tel = ContatoEmpresa(
                    empresa_id=empresa_id,
                    tipo_contato="TELEFONE",
                    valor=tel.strip(),
                    origem="RECEITA_FEDERAL",
                    principal=(idx == 0)
                )
                db.add(contato_tel)
                contatos_criados += 1

        # 3. Extrair Quadr de Sócios e Administradores (QSA)
        qsa = dados_api.get("qsa", [])
        for socio in qsa:
            nome_socio = socio.get("nome")
            cargo = socio.get("qualificacao")
            if nome_socio:
                contato_socio = ContatoEmpresa(
                    empresa_id=empresa_id,
                    tipo_contato="SOCIO_ADMINISTRADOR",
                    valor=f"{nome_socio} ({cargo})" if cargo else nome_socio,
                    origem="QSA_RECEITA",
                    principal=False
                )
                db.add(contato_socio)
                contatos_criados += 1

        db.commit()
        print(f"Sucesso: {contatos_criados} contatos salvos para a empresa ID {empresa_id}.")
    except Exception as e:
        db.rollback()
        print(f"Erro ao salvar contatos da empresa ID {empresa_id}: {e}")
    finally:
        db.close()