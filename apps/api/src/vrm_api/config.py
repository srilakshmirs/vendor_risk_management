"""Centralized settings — loaded from `.env` or process env."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


REPO_ROOT = Path(__file__).resolve().parents[4]  # apps/api/src/vrm_api/config.py -> repo
DATA_DIR = REPO_ROOT / "data"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(REPO_ROOT / ".env", Path(".env")),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- App ---
    app_name: str = "VRM Intelligence API"
    environment: Literal["dev", "staging", "prod"] = "dev"
    log_level: str = "INFO"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3001", "http://localhost:3000"])

    # --- Database ---
    # Postgres+pgvector (started via `make up` / `docker compose up postgres`).
    # Override with sqlite:///./vrm.db in .env if you want zero-Docker dev.
    database_url: str = "postgresql+psycopg://vrm:vrm@localhost:5432/vrm"

    # --- LLM provider toggle ---
    # `ollama` (local llama3.2) | `claude` (Anthropic API) | `mock` (canned responses)
    llm_provider: Literal["ollama", "claude", "mock"] = "ollama"

    # Anthropic
    anthropic_api_key: str | None = None
    claude_model_fast: str = "claude-haiku-4-5-20251001"
    claude_model_smart: str = "claude-sonnet-4-6"

    # Ollama
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2"

    # --- Startup behaviour ---
    # Pre-warm the embedder + LLM on FastAPI startup so the first /ask request
    # isn't a cold start. Fires as a background task — does NOT block startup.
    warmup_on_startup: bool = True

    # --- Data paths ---
    data_dir: Path = DATA_DIR
    vendor_registry_csv: Path = DATA_DIR / "vendor_registry.csv"
    vendor_labels_csv: Path = DATA_DIR / "vendor_labels.csv"

    # --- Scoring weights (tunable, sum should = 1.0) ---
    weight_breach: float = 0.30
    weight_data_access: float = 0.25
    weight_compliance: float = 0.20
    weight_financial: float = 0.15
    weight_operational: float = 0.10

    # --- Email notifications ---
    email_enabled: bool = True
    email_mode: Literal["smtp", "console"] = "console"  # console = log-only (no real SMTP)
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_use_tls: bool = True
    email_from: str = "vrm-alerts@socgen-hack.com"
    email_admin_recipients: list[str] = Field(default_factory=lambda: ["yaswanth@gmail.com"])
    email_send_to_vendor_contact: bool = False


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
