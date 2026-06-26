import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api.routes import router as api_router
from app.config import settings
from app.db.session import engine

logger = logging.getLogger("defi_scanner")


@asynccontextmanager
async def lifespan(app: FastAPI):  # type: ignore[arg-type]
    """Startup/shutdown logic for the FastAPI app."""
    import asyncio

    from app.collectors import run_collectors, shutdown_collectors

    # Test DB connection on startup
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        logger.info("Database connection OK")
    except Exception as e:
        logger.warning("Database not available at startup: %s", e)

    # Start collectors in background task
    collector_task = asyncio.create_task(run_collectors())
    logger.info("Collectors background task started")

    yield

    # Graceful shutdown
    await shutdown_collectors()
    try:
        await asyncio.wait_for(collector_task, timeout=10)
    except TimeoutError:
        logger.warning("Collectors did not shut down cleanly within timeout")
    await engine.dispose()


app = FastAPI(
    title="DeFi Alpha Scanner",
    lifespan=lifespan,
)

app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_ORIGIN],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {"status": "ok"}
