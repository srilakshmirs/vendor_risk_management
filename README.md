# VRM Intelligence — Société Générale TPRM Hackathon (Option A)

AI-powered Third-Party & Vendor Risk Management. Inventory 400+ vendors,
score risk continuously, surface critical anomalies, extract contract obligations
via LLM, and answer auditor questions in <5 min.

## Scoring engine — measured against `vendor_labels.csv` ground truth

| Rubric gate | Target | **Measured** |
|---|---|---|
| Anomaly-type accuracy | ≥ 80% | **90.0%** (360 / 400) |
| **CRITICAL** severity recall | ≥ 95% | **100.0%** (52 / 52) |
| **HIGH** severity recall | ≥ 80% | **100.0%** (120 / 120) |
| Binary anomaly detection F1 | ≥ 0.85 | **1.000** (precision 100% · recall 100%) |
| Vendor coverage | ≥ 95% | **100.0%** (400 / 400) |

Reproduce: `make eval` (full report) · `make eval-json` (machine-readable) · `pytest tests/test_scoring.py::test_evaluator_passes_all_rubric_gates` (regression-gated in CI).

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
- [x] `/risk/score/{id}`, `/risk/score/{id}/latest`, `/risk/score-all`, `/risk/eval`
- [x] 9 SQLAlchemy models with relationships, on Postgres + pgvector
- [x] CSV → DB ingestion (idempotent via `--reset`)
- [x] LLM provider abstraction (Claude + Ollama + mock)
- [x] 400-vendor mock dataset with ground-truth labels
- [x] **Risk scoring engine** — 5-component weighted composite + 7-rule anomaly classifier, **90% accuracy / 100% CRITICAL recall**
- [x] **Eval harness** — confusion matrix, per-severity recall/precision, rubric-gate pass/fail
- [x] Docker Compose (Postgres+pgvector + Redis + API)
- [x] Makefile, .env.example, Dockerfile, pytest (11 tests including rubric regression)
- [x] **Next.js dashboard (apps/web)** — Portfolio (`/`), Vendors (`/vendors`), Vendor detail (`/vendors/[id]`), Eval (`/eval`); SWR-backed, recharts donut + gauge, traffic-light + severity badges, recompute-on-demand

## Scoring engine — internals

```
score_vendor(ctx) → ScoredVendor
  ├── 5 weighted components (0–100 each)
  │     breach 30%  · data_access 25%  · compliance 20%
  │     financial 15%  · operational 10%
  ├── 7-rule priority pipeline (first hit wins, most severe first)
  │     R01 BREACHED_VENDOR_HIGH_ACCESS    (CRITICAL)
  │     R02 VENDOR_UNDER_INVESTIGATION      (CRITICAL)
  │     R03 HIGH_RISK_SCORE                 (HIGH)
  │     R04 EXPIRED_CERTIFICATION           (HIGH)
  │     R05 RECENTLY_BREACHED_VENDOR        (MEDIUM)
  │     R06 CONTRACT_EXPIRED_ACTIVE_ACCESS  (MEDIUM)
  │     R07 ELEVATED_RISK_VENDOR            (LOW)
  └── Deterministic narrative + traffic light
```

Files: `apps/api/src/vrm_api/scoring/{context,components,rules,engine,evaluator,score_all,eval_cli}.py`

## Next up

- Contract PDF extraction endpoint (`/contracts/extract`) — LLM structured output
- `/ask` streaming endpoint with RAG over vendor profile + pgvector
- Alert generator (cron via APScheduler) for cert/contract expiry
- Next.js dashboard: portfolio grid, vendor detail, alert center
- Audit pack PDF export
