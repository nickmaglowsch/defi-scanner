# Task 01: Repository Scaffold & Dev Environment

## Objective
Initialize the monorepo with FastAPI backend shell, Next.js frontend skeleton, and Docker Compose dev environment — `docker compose up` should start Postgres+TimescaleDB, a backend responding to `/health`, and a frontend dev server.

## Context
Greenfield repo. This task establishes every subsequent task's foundation: build tooling, config, database container, and the two app shells. See `updated-prd.md` Sections "Tech Stack" and "Monorepo Layout" for the target directory structure. All conventions from `shared-context.md` apply.

## Target Files
- `backend/pyproject.toml`
- `backend/uv.lock`
- `backend/app/__init__.py`
- `backend/app/main.py`
- `backend/app/config.py`
- `backend/app/db/__init__.py`
- `backend/app/db/session.py`
- `frontend/` (full Next.js project init via `create-next-app`)
- `docker-compose.yml`
- `.gitignore`

## Dependencies
None.

## Steps
1. Create `backend/pyproject.toml` with dependencies: `fastapi`, `uvicorn[standard]`, `sqlalchemy[asyncio]`, `asyncpg`, `alembic`, `web3`, `httpx`, `pydantic`, `pydantic-settings`, `ruff`, `black`, `pytest`, `pytest-asyncio`, `pytest-mock`, `httpx` (for TestClient). Use Python 3.12. Generate `uv.lock` with `uv lock`.
2. Add `[tool.ruff]` section to pyproject.toml: enable I (isort), F (pyflakes), E/W (pycodestyle), UP (pyupgrade). Set line-length 100. Format section for black-compatible output.
3. Write `backend/app/config.py`: Pydantic `BaseSettings` class reading:
   - `DATABASE_URL` (default `postgresql+asyncpg://defi:defi@localhost:5432/defi_scanner`)
   - `RPC_URL` (default `https://eth.llamarpc.com` — a public endpoint; document override)
   - `HYPERLIQUID_API_URL` (default `https://api.hyperliquid.xyz`)
   - `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` (default empty → alerts logged only)
   - `FRONTEND_ORIGIN` (default `http://localhost:3000`)
   - `COLLECTOR_INTERVAL_SECONDS` (default `300`)
   - `RANKER_WEIGHTS` (default JSON string with all weights = 1.0)
   All with `DEFI_` env prefix; use `model_config = {"env_prefix": "DEFI_"}`.
4. Write `backend/app/db/session.py`: create async SQLAlchemy engine from `DATABASE_URL`, `async_sessionmaker`, and an `async def get_db()` generator for FastAPI dependency injection. Use `NullPool` or default pooling — note tradeoff in comment.
5. Write `backend/app/main.py`:
   - FastAPI app with title "DeFi Alpha Scanner"
   - CORS middleware allowing `FRONTEND_ORIGIN`
   - `@app.get("/health")` returning `{"status": "ok"}`
   - `@app.on_event("startup")` to test DB connection (log success/warning)
   - Placeholder for collector scheduler (add comment `# task-03/04: start collectors in background task`)
6. Init frontend with `npx create-next-app@latest frontend --typescript --tailwind --eslint --app --src-dir --no-import-alias`. Then install `shadcn/ui` (init), `@tanstack/react-table`, `recharts`. Update `frontend/src/app/page.tsx` with a minimal "DeFi Alpha Scanner" heading.
   - Note: if `create-next-app` interactive prompts block, use flags shown above (Next.js 15 defaults to `--app`).
7. Write root `docker-compose.yml`:
   - `timescaledb`: image `timescale/timescaledb:latest-pg16`, port 5432, env POSTGRES_USER/PASSWORD/DB = defi/defi/defi_scanner, volume for data persistence, healthcheck
   - `backend`: build `./backend`, port 8000, depends_on timescaledb (condition: service_healthy), env vars for DATABASE_URL pointing to timescaledb service
   - `frontend`: build `./frontend`, port 3000, depends_on backend, env NEXT_PUBLIC_API_URL=http://backend:8000
   - For `backend/Dockerfile`: multi-stage, `python:3.12-slim`, copy pyproject + uv.lock, `uv sync --frozen`, copy app, CMD uvicorn. Keep it minimal (~10 lines).
   - For `frontend/Dockerfile`: standard Next.js Dockerfile (node:20-alpine, npm ci, build, CMD npm start). Use Next.js standalone output.
8. Write `.gitignore`: Python (`__pycache__`, `.venv`, `uv.lock` — actually keep uv.lock in repo), Node (`node_modules`, `.next`), env files (`.env` but keep `.env.example`), IDE files, `.DS_Store`.
9. Verify: `docker compose up` starts all three services; `curl localhost:8000/health` returns 200; `curl localhost:3000` returns Next.js page.

## Acceptance Criteria
- [ ] `docker compose up` starts Postgres+TimescaleDB, backend (uvicorn), and frontend (Next.js dev) without errors
- [ ] `GET /health` returns `{"status": "ok"}` and logs DB connection attempt
- [ ] Frontend renders at `localhost:3000` with Tailwind working and shadcn/ui init complete
- [ ] `ruff check backend/` passes with no errors
- [ ] `.gitignore` excludes node_modules, .next, __pycache__, .venv, .env
- [ ] All config values overridable via `DEFI_` prefixed env vars
