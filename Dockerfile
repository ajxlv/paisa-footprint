# API image: installs pf_core + api, and builds the fixture snapshot at image build time.
FROM python:3.12-slim

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    PF_SNAPSHOT_DIR=/app/data/snapshots/fixtures \
    PF_DEMO_DIR=/app/tests/fixtures/synthetic \
    PF_DOCS_DIR=/app/docs

COPY pyproject.toml README.md ./
COPY pf_core ./pf_core
COPY cli ./cli
COPY api ./api
RUN pip install --no-cache-dir .

COPY docs ./docs
COPY sql ./sql
COPY tests/fixtures ./tests/fixtures
RUN pf build-snapshot --input tests/fixtures/brsr --out "$PF_SNAPSHOT_DIR"

EXPOSE 8000
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
