# ───────────────────────────────────────────────────────────────────
# VRM Intelligence — orchestration commands
# ───────────────────────────────────────────────────────────────────
.PHONY: help install api web dev mock-data seed reset llm-info \
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

web:  ## Run Next.js dashboard
	bun run dev --filter=web

dev:  ## Convenience: print the two commands to run in separate terminals
	@echo "Run in 2 terminals:"
	@echo "  1) make api"
	@echo "  2) make web"

llm-info:  ## Probe the active LLM provider via /llm/info
	@curl -s http://localhost:8000/llm/info | python3 -m json.tool

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
