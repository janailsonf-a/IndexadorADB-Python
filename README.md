# 🔎 Noxis Backend

High-performance file indexing and search system built with FastAPI for large-scale environments.

---

## 🚀 Overview

Noxis is a backend system designed for high-performance file indexing and search in large-scale environments.

Instead of storing file contents, the system indexes only metadata, ensuring:

- ⚡ High performance  
- 💾 Low storage usage  
- 🔍 Fast search results  

---

## 🧠 Features

- 🔎 Search files by name, path, or extension  
- ⚡ Full-text search using SQLite FTS5  
- 📄 File preview (safe inline rendering)  
- ⬇️ File download with validation  
- 📊 System monitoring (CPU, RAM, Disk)  
- 🔐 Secure file handling (path traversal protection)  
- 🔄 Incremental indexing system  

---

## 🛠 Tech Stack

- Python  
- FastAPI  
- SQLite (FTS5)  
- Uvicorn  
- Docker (optional)  

---

## 🏗 Architecture

The project follows a modular architecture:

- **Repositories** → data access layer  
- **Services** → business logic  
- **Routes** → API endpoints  
- **Core** → configuration and constants  

This structure improves maintainability and scalability.

---

## 📦 Installation

```bash
git clone https://github.com/janailsonf-a/Noxis-Python
cd Noxis-Python

python -m venv .venv
source .venv/bin/activate  # Linux

pip install -r requirements.txt
```
---
## ▶️ Running
```bash
uvicorn app.main:app --reload

```
---
## 🔌 API Endpoints
| Endpoint    | Description    |
| ----------- | -------------- |
| `/search`   | Search files   |
| `/preview`  | Preview files  |
| `/download` | Download files |
| `/status`   | System metrics |
| `/health`   | Health check   |


---
## 📊 Performance
The system is optimized to handle millions of files by indexing only metadata, enabling fast queries and low resource consumption.

## 🔐 Security

- Protection against path traversal  
- File size validation  
- Safe file preview  


## 🌍 Use Cases

- Corporate file systems  
- Document indexing platforms  
- Internal search tools  
- Large-scale storage environments

## 🔗 Frontend

Frontend available at:
➡️ https://github.com/janailsonf-a/Noxis-Vue

## 👨‍💻 Author

Developed by Janailson Almeida
