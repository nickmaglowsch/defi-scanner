# Task 01: Repository Scaffold & Dev Environment

- **Decisions**:
  - Used `SettingsConfigDict(env_prefix="DEFI_")` instead of the `model_config` dict literal mentioned in the task spec — both are valid in pydantic-settings v2, and `SettingsConfigDict` is the recommended approach in newer versions. The task's intended behavior is identical.
  - Used `asynccontextmanager`-based `lifespan` instead of the deprecated `@app.on_event("startup")` pattern. FastAPI's `on_event` is deprecated since 0.107; the lifespan pattern is the modern equivalent and achieves the same startup DB connection test.
  - Used `--import-alias "@/*"` for create-next-app instead of `--no-import-alias` from the task step 6. `--no-import-alias` is not a recognized flag in Next.js 16's create-next-app; `@/*` is the standard alias used by shadcn/ui and matches project conventions.
  - `COLLECTOR_INTERVAL_SECONDS` typed as `int` for automatic coercion from env string.
  - Frontend Dockerfile CMD uses `-H 0.0.0.0` so the dev server is reachable from outside the container.
  
- **Deviations**:
  - Installed Next.js 16 (latest via `create-next-app@latest`) instead of the 15 referenced in shared-context. The task said `@latest`; Next.js 16 was released and the CLI auto-selected it. shadcn/ui v4.11.0 init worked correctly with Next.js 16 and Tailwind CSS v4.
  - `uv lock` resolved with Python 3.13 (the available `uv` uses CPython 3.13.13). The `pyproject.toml` sets `requires-python = ">=3.12"`, so this is compatible. Python 3.12 is only specified in the Dockerfile base image.
  - Backend Dockerfile uses `uv sync --frozen` — this requires `uv.lock` in the build context. Lockfile was generated successfully.
  - Did not attempt `docker compose up` (as instructed in environment notes). Compose config validates cleanly via `docker compose config`.

- **Trade-offs**: None — straightforward scaffold with no alternatives to weigh.

- **Risks**:
  - Next.js 16 + React 19 + Tailwind v4 is bleeding edge. shadcn/ui v4.11.0 init succeeded, but compatibility with TanStack Table and Recharts should be verified when task-09 adds the dashboard.
  - `uv.lock` is committed (461KB) — it's the correct behavior for reproducible builds, worth the repo size.
  - Frontend Dockerfile is dev-only (`npm run dev`). For production, task-09 or a future task should switch to Next.js standalone output with `npm run build && npm start`.
