# INT-Slim

INT-Slim is an AI-assisted learning platform built with FastAPI, Vue 3, MySQL, LangGraph, and Chroma. It provides multi-agent chat, shared knowledge retrieval, chapter-based learning, generated assessments, code practice, and a mistake notebook.

## Main features

- Multi-agent tutoring with streamed steps, source citations, pause/resume, and human confirmation.
- Shared and user-owned knowledge bases backed by MySQL metadata and Chroma vectors.
- Course and chapter reading flow with persistent progress.
- Reusable chapter quizzes and course exams with stored attempts and explanations.
- Python, C, C++, and Java code practice in ACM and LeetCode-style modes.
- Isolated Conda sandbox for code execution and evaluation.

## Repository layout

```text
backend/                 FastAPI application, agents, RAG, tools, and tests
backend/database/        Publishable schema and shared knowledge-base package
backend/scripts/         Database, knowledge-base, and sandbox setup utilities
frontend/                Vue 3 + Vite application
docs/                    Architecture and project documentation
```

Runtime data under `backend/sandbox/`, local backups, logs, generated frontend files, and real environment files are intentionally excluded from Git.

## Requirements

- Python 3.11+
- Node.js 20+
- MySQL 8.0+
- Conda or Miniconda (recommended for the multi-language sandbox)

## 1. Clone and configure

```powershell
git clone git@github.com:SuanXiangJi/INT-Slim.git
cd INT-Slim
Copy-Item backend/.env.example backend/.env
```

Edit `backend/.env`. At minimum, configure the six `mysql_*` values, `secret_key`, and one LLM provider key. Add `tavily_api_key` to enable web search and SMTP values to enable email verification.

## 2. Prepare MySQL

```powershell
mysql -u root -p -e "CREATE DATABASE xbots_v2 CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
mysql -u root -p xbots_v2 < backend/database/schema.sql
```

Restore the bundled shared knowledge base:

```powershell
cd backend
python scripts/system_kb_backup.py restore --input database/system_kb
cd ..
```

The package contains only public system learning material. It excludes accounts, password hashes, tokens, conversations, submissions, and user profiles. See [backend/database/README.md](backend/database/README.md) for maintenance commands.

## 3. Install dependencies

Backend:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
cd ..
```

Frontend:

```powershell
cd frontend
npm install
cd ..
```

Optional code-execution sandbox:

```powershell
powershell -ExecutionPolicy Bypass -File backend/scripts/setup_sandbox_env.ps1
```

The sandbox installs Python, Node.js, OpenJDK, GCC/G++, and the packages listed in `backend/sandbox-requirements.txt`. Details are in [backend/SANDBOX_ENV.md](backend/SANDBOX_ENV.md).

## 4. Run in development

Backend terminal:

```powershell
cd backend
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2
```

Frontend terminal:

```powershell
cd frontend
npm run dev -- --host 0.0.0.0 --port 5173
```

Open `http://localhost:5173`. API documentation is at `http://localhost:8000/api/v1/docs`, and health status at `http://localhost:8000/health`.

## Production-style local run

```powershell
cd frontend
npm run build
cd ../backend
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2
```

FastAPI serves the built SPA at `http://localhost:8000/app/`.

## Verification

```powershell
cd backend
python -m pytest -q
cd ../frontend
npm run build
```

## Security notes

- Never commit `backend/.env`, private database dumps, Chroma runtime files, logs, or sandbox sessions.
- Replace `secret_key` in every deployment.
- Run the code sandbox with a low-privilege OS account and external resource limits in production.
- Review public knowledge-base licensing and source metadata before redistributing updated datasets.
