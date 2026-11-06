import os
import sys
from logging.config import fileConfig
from dotenv import load_dotenv

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

# 1. Adiciona a raiz do projeto ao PATH do Python
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# 2. Carrega as variáveis do ficheiro .env
load_dotenv()

# 3. Importa a Base e os modelos ORM
from app.database.connection import Base
import app.models  # Carrega PublicacaoBruta, Empresa e Licenca

# Objeto de configuração do Alembic
config = context.config

# 4. Injeta a DATABASE_URL do .env na configuração do Alembic
database_url = os.getenv("DATABASE_URL")
if database_url:
    config.set_main_option("sqlalchemy.url", database_url)

# Configuração de logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# 5. Define os metadados dos nossos modelos para autogenerate
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Modo offline: gera scripts SQL sem abrir conexão direta."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Modo online: conecta à base PostgreSQL e aplica as alterações."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()