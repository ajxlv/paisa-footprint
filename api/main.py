"""Read-only FastAPI service over a Parquet snapshot.

The API never calls NSE or any other data source: it serves whatever snapshot `pf
build-snapshot` wrote. Portfolio computation runs the pure PCAF engine on user-supplied holdings
and EVIC values.

Environment:
    PF_SNAPSHOT_DIR   snapshot directory (default data/snapshots/fixtures)
    PF_DEMO_DIR       synthetic demo portfolios (default tests/fixtures/synthetic)
    PF_DOCS_DIR       docs directory holding METHODOLOGY.md (default docs)
    PF_CORS_ORIGINS   extra comma-separated CORS origins
"""

import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import companies, funds, portfolio
from api.state import AppState

DEV_ORIGINS = [
    "http://localhost:5173",  # vite dev
    "http://127.0.0.1:5173",
    "http://localhost:4173",  # vite preview
    "http://localhost:8080",  # docker compose web
]


def create_app(
    snapshot_dir: str | Path | None = None,
    demo_dir: str | Path | None = None,
    docs_dir: str | Path | None = None,
) -> FastAPI:
    """Build the app. Arguments override the PF_* environment variables (used by tests)."""
    app = FastAPI(
        title="Paisa Footprint API",
        version="0.2.0",
        description="Read-only PCAF financed emissions from BRSR filings. No live data calls.",
    )
    app.state.pf = AppState(
        snapshot_dir=Path(
            snapshot_dir or os.environ.get("PF_SNAPSHOT_DIR", "data/snapshots/fixtures")
        ),
        demo_dir=Path(demo_dir or os.environ.get("PF_DEMO_DIR", "tests/fixtures/synthetic")),
        docs_dir=Path(docs_dir or os.environ.get("PF_DOCS_DIR", "docs")),
    )
    extra = [o.strip() for o in os.environ.get("PF_CORS_ORIGINS", "").split(",") if o.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=DEV_ORIGINS + extra,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )
    for router in (companies.router, portfolio.router, funds.router):
        app.include_router(router)
    return app


app = create_app()
