# 🔎 Indexador

Sistema corporativo de indexação e busca de arquivos para ambientes com milhões de arquivos.

<p align="left">
  <img src="https://img.shields.io/badge/Python-3.12-blue?logo=python" />
  <img src="https://img.shields.io/badge/FastAPI-Backend-009688?logo=fastapi" />
  <img src="https://img.shields.io/badge/SQLite-FTS5-003B57?logo=sqlite" />
  <img src="https://img.shields.io/badge/Status-Production%20Ready-brightgreen" />
</p>

---

## 📌 Sobre o Projeto

O Indexador é um sistema desenvolvido para realizar indexação e busca eficiente de arquivos em ambientes corporativos com grande volume de dados.

O sistema armazena apenas **metadados**, garantindo baixo custo operacional e alta performance.

---

## ⚙️ Funcionalidades

- Busca rápida por nome, caminho ou extensão  
- Indexação apenas de metadados  
- Utilização de SQLite com FTS5  
- Monitoramento do status de indexação  
- Proteção contra path traversal  
- Reindexação segura  

---

## 🏗 Arquitetura

app/
├── main.py # API + Interface Web
├── indexer.py # Processo de indexação (CLI)
├── db.py # Schema e helpers do banco
├── templates/ # Interface HTML
└── static/ # Arquivos estáticos

file_index.db # Banco SQLite (metadados)

---

## 🚀 Instalação

```bash
git clone https://github.com/seu-usuario/indexador.git
cd indexador
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

ROOT_DIR=/caminho/dos/arquivos
DB_PATH=/caminho/do/banco/file_index.db

python -m app.indexer

Funcionalidades da indexação:
    - Incremental
    - Atualiza arquivos modificados
    - Remove arquivos deletados
    - Atualiza estatísticas automaticamente

Executando o Servidor
 - uvicorn app.main:app --host 0.0.0.0 --port 8000

Produção recomendada:
 - gunicorn -k uvicorn.workers.UvicornWorker app.main:app

## Melhorias implementadas nesta versão

- Removida a exposição direta de `ROOT_DIR` por rota estática pública.
- Novo endpoint seguro `GET /files/{path}` com validação contra path traversal.
- Bloqueio de preview para extensões não permitidas e arquivos acima do limite configurável.
- Busca agora funciona por `GET`, facilitando compartilhamento de URL e paginação estável.
- Adicionado ordenamento por relevância usando `bm25(files)` quando o FTS estiver disponível.
- Validação obrigatória de `ROOT_DIR` e `DB_PATH` no startup.
- Logging com arquivo rotativo em `logs/app.log`.
- `watcher.py` atualizado para usar `watchfiles` e o schemas atual de `files_meta`.

### Novas variáveis opcionais no `.env`

```env
LOG_LEVEL=INFO
LOG_PATH=logs/app.log
MAX_PREVIEW_SIZE_MB=50
MAX_DOWNLOAD_SIZE_MB=2048
```
