# ───────────────────────────────────────────────────────────────────
# VRM Intelligence — orchestration commands
# ───────────────────────────────────────────────────────────────────
.PHONY: help install api web docs dev mock-data seed reset llm-info \
        score-all eval eval-json risk-of \
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
