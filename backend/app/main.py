"""QistEngine API entrypoint."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import init_db
from app.ml.registry import registry
from app.routers import applications, health, ingestion, metrics, scoring


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    registry.load()  # best-effort; /health reports status if artifacts are missing
    yield


app = FastAPI(
    title="QistEngine API",
    version="1.0.0",
    description=(
        "AI-powered alternative credit scoring for unbanked individuals and "
        "micro-merchants in Pakistan. Demonstration model trained on synthetic "
        "data. Not a regulated credit decision."
    ),
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(scoring.router)
app.include_router(ingestion.router)
app.include_router(applications.router)
app.include_router(metrics.router)


@app.get("/")
def root() -> dict:
    return {
        "name": "QistEngine API",
        "docs": "/docs",
        "health": "/health",
        "disclaimer": "Demonstration model trained on synthetic data. Not a regulated credit decision.",
    }
