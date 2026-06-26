# Planning Questions

## Codebase Summary
Greenfield repository (`feat/defi-alpha-scanner` branch, one init commit). No existing code, conventions, or infrastructure. The MVP vertical slice must establish the full architecture shape: Spring Boot backend + PostgreSQL + Flyway + Next.js frontend in a single monorepo. One lending adapter (Aave V3) and one funding adapter (Hyperliquid) as concrete implementations, with interface seams for future protocols.

---

## Questions

### Q1: Monorepo layout — where do backend and frontend live?
**Context:** The PRD specifies a single repo containing both the Java backend and Next.js frontend. The directory structure will determine build tooling, Docker Compose paths, and developer ergonomics for the lifetime of the project.
**Options:**
- A) **Flat root**: `backend/` and `frontend/` at repo root. No monorepo tooling (no Turborepo, Nx). Each has its own build config. Simplest.
- B) **Packages-style**: `packages/backend/` and `packages/frontend/` with a root `package.json` (or `pnpm-workspace.yaml`) for shared scripts/linting. Adds tooling overhead but standardizes cross-package commands.
- C) **Polyglot monorepo tool**: Turborepo or Nx at root orchestrating both Maven/Gradle + npm/pnpm builds. Heavy initial config, but unified `turbo build` / `turbo test`.
**Recommendation:** A — Flat root. No orchestration tooling needed. Backend and frontend are built, tested, and deployed independently. A root `docker-compose.yml` ties them together for local dev. Add Turborepo/Nx only when the repo grows 3+ packages with shared deps.

---

### Q2: Java build tool — Maven or Gradle?
**Context:** Spring Boot is equally well-supported by both. The choice affects the entire backend module structure, dependency management, and task scripting.
**Options:**
- A) **Maven** (`pom.xml`) — Spring Initializr default. Declarative XML, simpler for single-module or few-module projects. Wider ecosystem of Spring Boot starters documented in Maven XML.
- B) **Gradle** (Groovy DSL) — More concise, faster incremental builds, better for multi-module builds with complex custom tasks.
- C) **Gradle** (Kotlin DSL) — Same as B but with type-safe build scripts, steeper learning curve if team isn't Kotlin-fluent.
**Recommendation:** A — Maven. The backend is a single-module (or at most 2-3 modules: core, adapters, api) Spring Boot app. Maven's convention-over-configuration matches the scope. No custom build logic anticipated that would justify Gradle's flexibility.

---

### Q3: JavaScript package manager — npm, pnpm, or yarn?
**Context:** The Next.js frontend needs a package manager. This affects lockfile format, install speed, and CI config.
**Options:**
- A) **npm** — Ships with Node.js. Zero install step. Sufficient for a single frontend package.
- B) **pnpm** — Faster, disk-efficient, strict dependency resolution. Overkill for one package, but scales well if a monorepo workspace emerges later.
- C) **yarn** — Comparable to pnpm. No clear advantage over npm for a single package.
**Recommendation:** A — npm. Already on the machine with Node.js. One less global tool to document in CONTRIBUTING.md. No workspace features needed yet.

---

### Q4: Aave V3 data source — how to fetch lending rates?
**Context:** Aave V3 data (deposit APY, borrow APY, utilization, TVL) can be read from multiple sources. Each has different reliability, rate-limiting, and data shape implications. This is the single most consequential integration design decision for the MVP.
**Options:**
- A) **The Graph subgraph** (GraphQL against Aave's official subgraph on The Graph Network or a hosted service). Structured, documented schema. No RPC needed. Free tier may rate-limit; paid API key available. Returns all needed fields in one query.
- B) **On-chain via Web3j** (Ethereum RPC call to Aave V3 Pool contract methods). Maximum decentralization, no intermediary. Requires an RPC provider (Infura, Alchemy) with its own rate limits. Contract ABIs needed. Each metric is a separate contract call — N+1 query problem unless batched via multicall.
- C) **Aave UI API** (unofficial REST endpoint used by app.aave.com). Reverse-engineered, no SLA, may break without notice. Not recommended for anything beyond prototyping.
**Recommendation:** A — The Graph subgraph. Single query returns all metrics per reserve. No RPC dependency, no ABI maintenance, no multicall complexity. Well-documented, versioned schema. The free tier's rate limit is fine for a periodic collector (every few minutes, not per-second). If rate-limited, add a paid API key later. Design the `LendingProvider` interface to accept a configurable GraphQL endpoint URL so Morpho/Spark subgraphs slot in later.

---

### Q5: TimescaleDB — use the actual extension or plain PostgreSQL?
**Context:** The PRD calls out TimescaleDB hypertables for time-series snapshots. For local dev, this means using the `timescale/timescaledb` Docker image instead of `postgres`. The extension must be enabled per-database with `CREATE EXTENSION IF NOT EXISTS timescaledb;`. Flyway can handle this in a migration.
**Options:**
- A) **Use TimescaleDB** — Docker image `timescale/timescaledb:pg16`, enable extension in first Flyway migration, create hypertables for `lending_snapshots` and `funding_snapshots`. Automatic time-based partitioning, built-in compression, fast time-range queries.
- B) **Plain PostgreSQL with timestamps** — Standard `postgres:16` image. Index the `observed_at` column with a BRIN or B-tree index. No hypertable. Simpler Docker setup, no extension dependency. Adequate for MVP data volumes (snapshots every few minutes for 2 markets = ~30k rows/month).
**Recommendation:** A — TimescaleDB. The Docker image swap is trivial (`timescale/timescaledb:latest-pg16` instead of `postgres:16`). The `CREATE EXTENSION` migration is one line. Hypertables and automatic partitioning are genuinely useful for the time-range queries the dashboard charts will run. If the extension is unavailable in a specific environment, fallback to plain Postgres is straightforward — just skip `create_hypertable()`.

---

### Q6: Collector resilience — what happens when Aave/Hyperliquid APIs fail or rate-limit?
**Context:** External API calls will occasionally fail (network blip, rate limit, API downtime). The collector must not crash the application, and the system should degrade gracefully — ideally still serving the last known good data.
**Options:**
- A) **Retry + skip** — 3 retries with exponential backoff (1s, 2s, 4s). On exhaustion, log the error and skip this cycle. The API returns 200 with the most recent snapshot (which may be stale). No persistent cache; callers see data age and decide.
- B) **Retry + stale cache** — Same retry strategy, but persist the last successful response. On failure, serve the cached value with a `stale: true` flag in the API response. Adds a cache layer (in-memory map or Redis if available).
- C) **Circuit breaker** — Full resilience pattern (Resilience4j). After N consecutive failures, stop calling the external API for a cooldown period. Over-engineered for a read-only scanner where stale data is acceptable.
**Recommendation:** A — Retry + skip. Three retries with backoff in the collector's HTTP call wrapper. On failure, the collector logs and moves on. The API serves the most recent snapshot by `MAX(observed_at)` — naturally stale if the latest collection failed. The dashboard can show "last updated: X minutes ago" so users know data freshness. No extra cache infrastructure. This is the laziest working solution; upgrade to B only if users complain about gaps.

---

### Q7: API authentication — public or protected?
**Context:** The MVP serves read-only market data and opportunity rankings. No user accounts, no wallets, no write operations. Whether to add any auth layer affects the Spring Security config, CORS setup, and frontend fetch logic.
**Options:**
- A) **No auth** — Public, open API. CORS configured to allow the Next.js origin. Zero auth infrastructure. Simplest possible setup.
- B) **API key via header** — A single static API key (`X-API-Key` header) configured via environment variable. Frontend includes it in all requests. Trivial to implement with a Spring Security filter, stops casual scraping.
- C) **JWT + user accounts** — Full auth with login, user management, token refresh. Massively over-scoped for an MVP with no user data.
**Recommendation:** A — No auth. The system is read-only and serves public DeFi data. No PII, no write operations, no per-user state. CORS to allow the frontend origin. Add an API key later if the endpoint gets hammered by bots. Skip Spring Security entirely for the MVP — a simple CORS filter is enough.

---

### Q8: HTTP client for the Java backend — which library?
**Context:** Collectors need to make outbound HTTP calls to The Graph subgraph (GraphQL POST), Hyperliquid REST API (GET), and Telegram webhook (POST). Spring Boot offers several options, each with different ergonomics.
**Options:**
- A) **RestTemplate** — Synchronous, blocking. Spring's legacy HTTP client. Simple API, well-known. Being phased out in favor of WebClient, but still fully supported.
- B) **WebClient** — Spring's reactive, non-blocking client. Modern API, supports sync and async usage. The recommended replacement for RestTemplate. Requires `spring-boot-starter-webflux` dependency (pulls in Netty).
- C) **JDK `HttpClient` (Java 11+)** — Built into the JDK. No extra dependency. Supports HTTP/2, async. Less ergonomic than Spring options for JSON deserialization.
- D) **OkHttp** — Popular third-party library. Clean API, connection pooling, retry interceptor support. Requires an extra dependency.
**Recommendation:** B — WebClient. It's Spring's recommended HTTP client going forward, integrates natively with Spring Boot's autoconfiguration, supports easy JSON deserialization via Jackson, and can be used synchronously with `.block()` for collector use cases (no need for full reactive pipeline). The WebFlux starter dependency is lightweight.

---

### Q9: Risk score volatility input — compute or skip for MVP?
**Context:** The opportunity scoring formula includes `volatility_penalty` which requires historical price/rate volatility data — something we don't have until we've been collecting for a while. This input fundamentally differs from other inputs (yield, liquidity, TVL) which come from a single snapshot.
**Options:**
- A) **Skip volatility_penalty for MVP** — Remove it from the score formula. Compute the score from the remaining inputs (yield, liquidity, TVL, stability, utilization, protocol risk). Add volatility once enough historical data exists (e.g., after 30 days of snapshots).
- B) **Compute from funding rate volatility** — Use the standard deviation of funding rate snapshots we've collected so far as a proxy. Requires at least ~20 snapshots before the metric is meaningful. Results in a zero penalty for the first hour of operation.
- C) **Fetch external price data** — Integrate an oracle/price feed (e.g., Chainlink, CoinGecko API) to compute asset price volatility. Adds a new external dependency and data source for the MVP.
**Recommendation:** B — Compute from our own funding rate snapshots. It's zero-cost (we already collect the data), requires no new external integrations, and becomes more accurate over time. During the initial bootstrap period (~20 snapshots), return a zero volatility_penalty (neutral). This is a single SQL `STDDEV(funding_rate) OVER (LAST 20 ROWS)` query. The formula weight stays in config, so if the proxy proves noisy, it can be disabled by setting the weight to 0.

---

### Q10: TDD mode?
**Context:** The scoping decision highlights that calculation logic (looping, carry, opportunity scoring) must be covered by unit tests. TDD mode means writing failing tests before implementation code for each task.
**Options:**
- A) **Yes — TDD mode** — Each functional task writes a failing test first, confirms it fails, then writes the implementation. Guarantees test coverage on all calculation logic.
- B) **No — write tests after or alongside** — Implement first, then add tests. Faster initial velocity, lower cognitive overhead per task.
**Recommendation:** A — TDD mode. The calculation engine is pure, deterministic math (no I/O, no side effects) — the ideal candidate for TDD. The adapter layer (HTTP calls to Aave/Hyperliquid) is less suited for strict TDD since it requires mocking, but the pure calculation layer (LoopingSimulator, CarryCalculator, OpportunityRanker) benefits enormously from test-first. This aligns with the scoping decision's emphasis on tested calculations.
