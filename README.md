🔎 Enterprise File Indexer
Sistema Corporativo de Indexação e Busca de Arquivos
<p align="left"> <img src="https://img.shields.io/badge/Python-3.12-blue?logo=python" /> <img src="https://img.shields.io/badge/FastAPI-Backend-009688?logo=fastapi" /> <img src="https://img.shields.io/badge/SQLite-FTS5-003B57?logo=sqlite" /> <img src="https://img.shields.io/badge/Status-Production%20Ready-brightgreen" /> <img src="https://img.shields.io/badge/License-Private-red" /> </p>
📌 Sobre o Projeto

O Enterprise File Indexer é um sistema corporativo de indexação de arquivos projetado para ambientes com milhões de arquivos.

Ele:

🔎 Permite busca rápida por nome, caminho ou extensão

📂 Indexa metadados (não armazena arquivos)

⚡ Utiliza FTS5 para busca performática

📊 Fornece monitoramento de CPU, RAM e disco

🧾 Registra histórico de atividades

🛡️ Possui proteção contra path traversal

O sistema foi projetado para ser escalável, seguro e reindexável.

🏗 Arquitetura

O projeto é dividido em dois módulos principais:

├── app/
│   ├── main.py          → API FastAPI + Interface Web
│   ├── indexer.py       → Processo de indexação CLI
│   ├── db.py            → Schema e helpers do banco
│   ├── templates/       → Interface HTML (Jinja2)
│   └── static/          → CSS e assets
│
└── file_index.db        → Banco SQLite (metadados)

🔄 Fluxo de Funcionamento

O indexador percorre o filesystem

Metadados são salvos no SQLite

Interface web consulta:

FTS (Full Text Search)

Fallback LIKE

Atividades são registradas

Monitoramento exibe status em tempo real

🗄 Banco de Dados
files_meta

Armazena metadados dos arquivos.

Campo	Tipo
filename	TEXT
rel_path	TEXT
ext	TEXT (normalizado)
size_bytes	INTEGER
created_at	TEXT
modified_at	TEXT
mtime_ns	INTEGER
path_hash	TEXT
files (FTS5)

Responsável pela busca full-text performática.

indexer_status

Controla execução do indexador:

arquivos processados

total estimado

tempo de execução

estatísticas da última execução

activities

Log de ações do usuário:

search

preview

download

vacuum

clear_activities

🚀 Instalação
1️⃣ Clone o projeto
git clone https://github.com/seu-usuario/enterprise-file-indexer.git
cd enterprise-file-indexer

2️⃣ Crie o ambiente virtual
python -m venv .venv
source .venv/bin/activate

3️⃣ Instale dependências
pip install -r requirements.txt

4️⃣ Configure o .env
ROOT_DIR=/caminho/dos/arquivos
DB_PATH=/var/lib/indexador/file_index.db

▶️ Executando o Indexador
python -m app.indexer


✔️ Indexação incremental
✔️ Atualiza arquivos modificados
✔️ Remove deletados
✔️ Atualiza status

🌐 Executando o Servidor
uvicorn app.main:app --host 0.0.0.0 --port 8000

Produção recomendada:
gunicorn -k uvicorn.workers.UvicornWorker app.main:app

🔍 Como Funciona a Busca

A busca segue esta ordem:

Detecta busca por extensão

Tenta FTS (Full Text Search)

Se não houver resultado → fallback LIKE

Ordena por data (recente/antigo)

Extensões são normalizadas:

ext = ext.lower().lstrip(".")

📊 Escalabilidade
Estimativa de uso de armazenamento (metadados)
Arquivos	Tamanho estimado DB
1 milhão	~600MB
10 milhões	~6GB
40 milhões	~25–40GB

⚠️ O sistema não copia arquivos, apenas metadados.

🔒 Segurança

Proteção contra path traversal

Lock para evitar múltiplos indexadores simultâneos

Bloqueio de preview para arquivos > 2GB

Banco reindexável (não é crítico)

📈 Diferenciais Técnicos

Arquitetura simples e robusta

Baixo custo operacional

Independente do storage

Alta performance de leitura

Fácil manutenção

Reindexação segura

🛠 Possíveis Evoluções

PostgreSQL para >100M arquivos

ElasticSearch

Redis cache

Indexação distribuída

Clusterização

👨‍💻 Autor

Janailson Firmino de Almeida
Backend Developer# Indexador---Amigos-do-bem
