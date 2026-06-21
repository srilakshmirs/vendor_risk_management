# ───────────────────────────────────────────────────────────────────
# VRM Intelligence — orchestration commands
# ───────────────────────────────────────────────────────────────────
.PHONY: help install api web docs dev mock-data sample-contracts seed reset llm-info \
        score-all eval eval-json risk-of ask-reindex ask \
        alerts-sweep breach-poll alerts-count audit-pdf enhance \
        financial-scrape cert-verify \
        demo-reset \
        test lint format up down logs clean

API_DIR := apps/api
DATA_DIR := data

help:  ## Show this help
	@awk 'BEGIN {FS = ":.*##"; printf "\nUsage:\n  make \033[36m<target>\033[0m\n\nTargets:\n"} \
	     /^[a-zA-Z_-]+:.*?##/ { printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2 }' $(MAKEFILE_LIST)

# ── Setup ──
install:  ## Install JS (bun) + Python (uv) deps
	bun install
	cd $(API_DIR) && uv sync

# ── Data ──
mock-data:  ## Regenerate vendor_registry.csv + vendor_labels.csv (400 vendors, seed=42)
	uv run $(DATA_DIR)/generate_mock_data.py

sample-contracts:  ## Regenerate data/contracts/sample-msa.pdf + sample-msa-risky.pdf
	uv run $(DATA_DIR)/contracts/generate_sample_contracts.py

seed:  ## Load CSV into DB (drops + recreates tables)
	cd $(API_DIR) && uv run python -m vrm_api.seeds.ingest_csv --reset

# ── Dev runners ──
api:  ## Run FastAPI in dev mode (reload on save)
	cd $(API_DIR) && uv run uvicorn vrm_api.main:app --reload --host 0.0.0.0 --port 8000 --app-dir src

web:  ## Run Next.js dashboard (also rebuilds @repo/ui styles first)
	cd packages/ui && bun run build:styles
	bun run dev --filter=web

docs:  ## Run Fumadocs site
	bun run dev --filter=docs

dev:  ## Convenience: print the three commands to run in separate terminals
	@echo "Run in separate terminals:"
	@echo "  1) make api"
	@echo "  2) make web"
	@echo "  3) make docs"

llm-info:  ## Probe the active LLM provider via /llm/info
	@curl -s http://localhost:8000/llm/info | python3 -m json.tool

# ── Risk scoring ──
score-all:  ## Score every vendor and persist a RiskAssessment row
	cd $(API_DIR) && uv run python -m vrm_api.scoring.score_all --replace

eval:  ## Evaluate scoring engine vs vendor_labels.csv (ASCII report)
	cd $(API_DIR) && uv run python -m vrm_api.scoring.eval_cli

eval-json:  ## Same eval, JSON output to docs/eval_report.json
	@mkdir -p docs
	cd $(API_DIR) && uv run python -m vrm_api.scoring.eval_cli --json > ../../docs/eval_report.json
	@echo "→ docs/eval_report.json"

risk-of:  ## Show the latest risk score for a vendor: make risk-of VID=V0100
	@curl -s "http://localhost:8000/risk/score/$(VID)/latest" | python3 -m json.tool

# ── RAG / Ask ──
ask-reindex:  ## Build the embeddings table from current vendor data
	cd $(API_DIR) && uv run python -m vrm_api.rag.indexer

ask:  ## One-shot ask via /ask endpoint: make ask Q="Which vendors are CRITICAL?"
	@curl -s -X POST "http://localhost:8000/ask" \
	   -H "Content-Type: application/json" \
	   -d "{\"question\": \"$(Q)\", \"k\": 8}" | python3 -m json.tool

# ── Alerts + continuous monitoring ──
alerts-sweep:  ## Manually run cert/contract expiry sweep
	cd $(API_DIR) && uv run python -m vrm_api.services.expiry_sweep

breach-poll:  ## Manually poll the mock breach feed (also rescores affected vendors)
	cd $(API_DIR) && uv run python -m vrm_api.services.breach_feed

financial-scrape:  ## Manually poll the mock public-records financial health scraper
	cd $(API_DIR) && uv run python -m vrm_api.services.financial_scraper

cert-verify:  ## Manually poll the mock third-party SOC2/ISO/PCI verification service
	cd $(API_DIR) && uv run python -m vrm_api.services.cert_verifier

alerts-count:  ## Show open / by-severity / by-type alert counts
	@curl -s http://localhost:8000/alerts/count | python3 -m json.tool

# ── Audit pack PDF ──
audit-pdf:  ## Download a vendor audit pack PDF: make audit-pdf VID=V0007
	@mkdir -p docs/exports
	@curl -fsS -OJ "http://localhost:8000/audit/pack/$(VID)" --output-dir docs/exports
	@ls -lh docs/exports/audit-$(VID)-*.pdf | tail -1

enhance:  ## LLM-enhance the risk narrative for a vendor: make enhance VID=V0276
	@curl -fsS -X POST "http://localhost:8000/risk/score/$(VID)/enhance" | python3 -m json.tool

# ── Demo readiness ──
# Bullet-proof one-command reset before the live demo. Idempotent; safe to re-run.
# Destructive: wipes & re-seeds vendors. Runs without the FastAPI process being up.
# Hero vendors (V0276 ransomware + V0007 password dump) get pre-enhanced narratives
# so the first click on either one already shows the AI text without the wait.
HERO_VENDORS ?= V0276 V0007

demo-reset:  ## Full demo prep — wipes data, re-seeds, scores, indexes, alerts, breaches, enhances hero vendors
	@echo ""
	@echo "==> 1/9  Ensuring Postgres is up..."
	@docker compose up -d postgres >/dev/null 2>&1 || echo "    (docker compose unavailable — assuming Postgres is reachable on :5432)"
	@printf "    "; until docker exec vrm-postgres pg_isready -U vrm -d vrm >/dev/null 2>&1; do printf "."; sleep 1; done; echo " ready"
	@echo ""
	@echo "==> 2/9  Seeding 400 vendors (drops + recreates tables)..."
	@cd $(API_DIR) && LOG_LEVEL=WARNING uv run python -m vrm_api.seeds.ingest_csv --reset 2>&1 | grep -E "vendors|certifications|contracts|breaches|data_access" | tail -6
	@echo ""
	@echo "==> 3/9  Scoring all vendors (rules-v1.1)..."
	@cd $(API_DIR) && LOG_LEVEL=WARNING uv run python -m vrm_api.scoring.score_all --replace 2>&1 | grep -E "vendors|assessments" | tail -3
	@echo ""
	@echo "==> 4/9  Reindexing embeddings for /ask..."
	@cd $(API_DIR) && LOG_LEVEL=WARNING uv run python -m vrm_api.rag.indexer 2>&1 | grep -E "vendors|chunks" | tail -3
	@echo ""
	@echo "==> 5/9  Sweeping cert/contract expiries (60/30/7 day alerts)..."
	@cd $(API_DIR) && LOG_LEVEL=WARNING uv run python -m vrm_api.services.expiry_sweep 2>&1 | grep -E "considered|created|skipped" | tail -3
	@echo ""
	@echo "==> 6/9  Polling mock breach feed (auto-rescores affected vendors)..."
	@cd $(API_DIR) && LOG_LEVEL=WARNING uv run python -m vrm_api.services.breach_feed 2>&1 | grep -E "entries|ingested|rescored" | tail -3
	@echo ""
	@echo "==> 7/9  Polling mock public-records financial scraper..."
	@cd $(API_DIR) && LOG_LEVEL=WARNING uv run python -m vrm_api.services.financial_scraper 2>&1 | grep -E "entries|updated|alerts_raised|rescored" | tail -4
	@echo ""
	@echo "==> 8/9  Verifying SOC 2 / ISO / PCI status via mock third-party API..."
	@cd $(API_DIR) && LOG_LEVEL=WARNING uv run python -m vrm_api.services.cert_verifier 2>&1 | grep -E "entries|updated|alerts_raised|rescored" | tail -4
	@echo ""
	@echo "==> 9/9  LLM-enhancing hero vendor narratives ($(HERO_VENDORS)) — slow on Ollama, fast on Claude..."
	@cd $(API_DIR) && LOG_LEVEL=WARNING uv run python -m vrm_api.scoring.enhance_cli $(HERO_VENDORS) 2>&1 | grep -E "✓|✗|Enhancing"
	@echo ""
	@echo "✅ Demo data ready."
	@echo "   Hero vendors: $(HERO_VENDORS)"
	@echo "   Try:  make api  +  make web  →  http://localhost:3000"
	@echo "   Or test:  curl http://localhost:8000/alerts/count | python3 -m json.tool"

# ── Quality ──
test:  ## Run API tests
	cd $(API_DIR) && uv run pytest -v

lint:  ## Ruff lint
	cd $(API_DIR) && uv run ruff check src tests

format:  ## Ruff format
	cd $(API_DIR) && uv run ruff format src tests

# ── Docker ──
up:  ## docker compose up (full stack: Postgres+pgvector + Redis + API)
	docker compose up --build -d

down:  ## docker compose down
	docker compose down

logs:  ## tail docker logs
	docker compose logs -f --tail=200

# ── Cleanup ──
clean:  ## Remove local SQLite DB + caches
	rm -f $(API_DIR)/vrm.db
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
	rm -rf $(API_DIR)/.pytest_cache $(API_DIR)/.ruff_cache $(API_DIR)/.mypy_cache
