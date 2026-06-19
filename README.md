# VRM Intelligence — Société Générale TPRM Hackathon (Option A)

AI-powered Third-Party & Vendor Risk Management. Inventory 400+ vendors,
score risk continuously, surface critical anomalies, extract contract obligations
via LLM, and answer auditor questions in <5 min.

> Targets the hackathon rubric directly: **95%+ vendor coverage, 80%+ risk
> accuracy, 30+ day alert lead time, <5 min Q&A, <15 min audit report**.

## Stack

| Layer | Choice |
|---|---|
| Monorepo | Turborepo (Bun) |
| Web (`apps/web`) | Next.js 16 · React 19 · Tailwind 4 |
| API (`apps/api`) | FastAPI · SQLAlchemy 2.0 · Pydantic v2 · structlog |
| Data | SQLite (default) or Postgres + pgvector via Docker |
| LLM | **Selectable** — local Ollama (`llama3.2`) or Anthropic Claude (Haiku 4.5 / Sonnet 4.6), with `mock` for CI |
| Python tooling | `uv` for env + run |

## Project layout

```
vendor_risk_management/
├── apps/
│   ├── api/                          # FastAPI backend (Python, uv-managed)
│   │   ├── src/vrm_api/
│   │   │   ├── main.py               # FastAPI entrypoint, CORS, request logging
│   │   │   ├── config.py             # Settings via pydantic-settings (.env)
│   │   │   ├── db.py                 # SQLAlchemy engine + session
│   │   │   ├── logging_config.py     # structlog JSON / dev console
│   │   │   ├── models/               # 9 ORM tables (vendor, contract, cert, …)
│   │   │   ├── schemas/              # Pydantic response models
│   │   │   ├── routers/              # /healthz, /vendors, /llm/info
│   │   │   ├── llm/                  # Provider abstraction
│   │   │   │   ├── base.py           #   ABC: complete / extract_json / stream
│   │   │   │   ├── claude.py         #   Anthropic + prompt-cache
│   │   │   │   ├── ollama.py         #   Local llama3.2 (native JSON mode)
│   │   │   │   ├── mock.py           #   Canned responses (offline / CI)
│   │   │   │   └── factory.py        #   LLM_PROVIDER env var picks one
│   │   │   └── seeds/ingest_csv.py   # Loads vendor_registry.csv → DB
│   │   ├── tests/                    # pytest
│   │   ├── pyproject.toml            # uv-managed deps
│   │   └── Dockerfile                # multi-stage uv build
│   ├── web/                          # Next.js dashboard (scaffolded by Turborepo)
│   └── docs/                         # Turborepo template (kept; remove if unused)
├── packages/                         # Shared UI + configs (Turborepo defaults)
├── data/
│   ├── generate_mock_data.py         # PEP-723 inline-metadata script
│   ├── vendor_registry.csv           # 400 vendors (generated, seed=42)
│   └── vendor_labels.csv             # ground truth: 7 anomaly types, severity
├── docker-compose.yml                # Postgres+pgvector + Redis + API
├── Makefile                          # one-command operations
├── .env.example                      # all env vars documented
└── README.md
```

## Quickstart

### 1. Install everything

```bash
make install   # bun install (monorepo) + uv sync (apps/api)
```

### 2. (Re)generate mock data

```bash
make mock-data
# → 400 vendors, 7 anomaly types, 80% anomaly rate (deterministic seed=42)
```

### 3. Pick your LLM

```bash
cp .env.example .env
```

Edit `.env`:

| Provider | Set | Need |
|---|---|---|
| `ollama` (default) | `LLM_PROVIDER=ollama` | Local Ollama daemon + `ollama pull llama3.2` |
| `claude` | `LLM_PROVIDER=claude` + `ANTHROPIC_API_KEY=sk-ant-…` | Anthropic API key |
| `mock` | `LLM_PROVIDER=mock` | nothing — runs offline |

### 4. Seed the DB

```bash
make seed   # drops + recreates tables, loads 400 vendors from data/vendor_registry.csv
```

### 5. Run the API

```bash
make api
# → http://localhost:8000
# → http://localhost:8000/docs   (OpenAPI / Swagger UI)
# → http://localhost:8000/healthz
# → http://localhost:8000/llm/info
# → http://localhost:8000/vendors?sort=preliminary_risk_score:desc&limit=10
```

### 6. Run the web dashboard

```bash
make web    # → http://localhost:3001
```

## Full stack with Docker (production-ish)

```bash
make up     # postgres+pgvector + redis + api, all wired
make logs   # follow
make down
```

Switches `DATABASE_URL` to Postgres automatically inside the compose network.
The host's Ollama daemon is reachable from containers as `host.docker.internal:11434`.

## Test

```bash
make test   # pytest (FastAPI TestClient)
make lint   # ruff
```

## LLM toggle in code

The entire codebase calls `get_llm()` — no provider branching anywhere else:

```python
from vrm_api.llm import get_llm

llm = get_llm()                   # ClaudeProvider | OllamaProvider | MockProvider
resp = await llm.complete(system, user, prefer_smart=True)   # Sonnet 4.6 if claude
data = await llm.extract_json(system, user, schema_hint)     # native JSON mode for Ollama
async for chunk in llm.stream(system, user):                 # for the "Ask" UI
    print(chunk, end="")
```

## What's wired now

- [x] FastAPI app with CORS, request-id middleware, structlog
- [x] `/healthz`, `/readyz`, `/llm/info`, `/vendors`, `/vendors/{id}`
- [x] 9 SQLAlchemy models with relationships
- [x] CSV → DB ingestion (idempotent via `--reset`)
- [x] LLM provider abstraction (Claude + Ollama + mock)
- [x] 400-vendor mock dataset with ground-truth labels
- [x] Docker Compose (Postgres+pgvector + Redis + API)
- [x] Makefile, .env.example, Dockerfile, pytest

## Next up

- Risk scoring engine (composite + Isolation Forest) + eval harness against `vendor_labels.csv`
- Contract PDF extraction endpoint (`/contracts/extract`)
- `/ask` streaming endpoint with RAG over vendor profile + pgvector
- Alert generator (cron via APScheduler) for cert/contract expiry
- Next.js dashboard: portfolio grid, vendor detail, alert center
- Audit pack PDF export
