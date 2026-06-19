# Multi-stage build using uv — fast, deterministic, slim runtime.
FROM python:3.13-slim AS builder

ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PROJECT_ENVIRONMENT=/opt/venv

RUN pip install --no-cache-dir uv==0.8.11

WORKDIR /app
COPY pyproject.toml uv.lock* ./
RUN uv sync --frozen --no-install-project || uv sync --no-install-project

COPY src ./src
RUN uv sync --no-dev

# ---------- Runtime ----------
FROM python:3.13-slim AS runtime

RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

COPY --from=builder /opt/venv /opt/venv
COPY --from=builder /app/src /app/src
WORKDIR /app

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --start-period=10s \
  CMD curl -fsS http://localhost:8000/healthz || exit 1

CMD ["uvicorn", "vrm_api.main:app", "--host", "0.0.0.0", "--port", "8000", "--app-dir", "src"]
