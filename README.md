# EcoProspect — Inteligência de Prospecção Comercial Ambiental

O **EcoProspect** é uma plataforma SaaS _multi-tenant_ desenvolvida para monitorar publicações de órgãos ambientais (como o IAT/DIOE-PR), estruturar dados de licenças e empresas, e automatizar a prospecção de clientes para consultorias ambiental e empresas de engenharia.

---

## Tecnologias Utilizadas

- **Linguagem:** Python 3.14+
- **Framework Web & API:** FastAPI (em breve)
- **Banco de Dados:** PostgreSQL 16 (Docker)
- **ORM & Migrações:** SQLAlchemy 2.0 / Alembic
- **Parser & Extrator:** PyPDF / Regex Otimizado
- **Versionamento:** Git & GitHub

---

## Status do Desenvolvimento (Roadmap)

- [x] **Bloco 1 — Coleta e Armazenamento Bruto (DIOE/PR):** Ingestão resiliente da API e fallback via PDF para tabela PostgreSQL `publicacoes_brutas`.
- [x] **Bloco 2 — Tratamento, Normalização e Deduplicação:** Estruturação de `empresas` e `licencas` com busca textual otimizada.
- [x] **Bloco 3 — Controle de Validade e Vencimentos:** Regras de 120 dias (Decreto 9.541/2025) e identificação de renovações.
- [ ] **Bloco 4 — Inteligência Comercial:** Scoring de oportunidade por perfil de serviços.
- [ ] **Bloco 5 — Pesquisa Automática de Contatos:** Enriquecimento de contatos comerciais públicos.
- [ ] **Bloco 6 — Gestão de Oportunidades & Pipeline:** Gestão multi-tenant de leads.
- [ ] **Bloco 7 — Comunicação Comercial:** Geração e aprovação humana pré-envio.
- [ ] **Bloco 8 — Automação & Interface:** Painel, agendamento semanal e Chat.

---

## 💻 Como Rodar o Banco de Dados Localmente

```bash
# Subir os containers do PostgreSQL e pgAdmin
docker compose up -d

# Inicializar as tabelas no banco de dados
python -m app.database.init_db

# Testar o coletor bruto (Bloco 1)
python -m app.collectors.dioe_pr
```
