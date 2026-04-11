"""
Application settings from environment variables and optional ``.env`` in this directory.

``load_dotenv`` fills missing keys only (it does not override existing OS variables).

Requires: ``python-dotenv`` (no pydantic-settings dependency — avoids broken installs
or activating the wrong virtualenv).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

_ROOT = Path(__file__).resolve().parent
load_dotenv(_ROOT / ".env", override=False)


def _env_str(key: str, default: str = "") -> str:
    raw = os.environ.get(key)
    if raw is None:
        return default
    return raw.strip()


def _env_bool(key: str, default: bool = False) -> bool:
    raw = os.environ.get(key)
    if raw is None or str(raw).strip() == "":
        return default
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


def _env_int(key: str, default: int) -> int:
    raw = os.environ.get(key)
    if raw is None or str(raw).strip() == "":
        return default
    return int(raw)


def _env_float(key: str, default: float) -> float:
    raw = os.environ.get(key)
    if raw is None or str(raw).strip() == "":
        return default
    return float(raw)


def _env_llm_mode() -> str:
    s = _env_str("RECEIPT_LLM_MODE", "off").lower()
    if s not in ("off", "fallback", "always"):
        return "off"
    return s


@dataclass(frozen=True)
class Settings:
    database_url: str
    sql_echo: bool
    receipt_llm_mode: str
    ollama_url: str
    ollama_model: str
    ollama_timeout_sec: float
    ollama_max_retries: int
    use_llm_process_bill: bool
    ocr_debug: bool
    ocr_min_confidence: float
    ocr_preprocess_max_side: int
    paddle_pdx_disable_model_source_check: bool
    cors_allow_origins: str
    log_level: str
    upload_folder: str
    uvicorn_host: str
    uvicorn_port: int


@lru_cache
def get_settings() -> Settings:
    database_url = _env_str("DATABASE_URL")
    if not database_url:
        raise RuntimeError(
            "DATABASE_URL is not set. Create BillScannerServer/.env from .env.example "
            "(see DATABASE_URL=...) or export DATABASE_URL before starting the app."
        )

    return Settings(
        database_url=database_url,
        sql_echo=_env_bool("SQL_ECHO", False),
        receipt_llm_mode=_env_llm_mode(),
        ollama_url=_env_str("OLLAMA_URL", "http://127.0.0.1:11434/api/generate"),
        ollama_model=_env_str("OLLAMA_MODEL", "llama3.2"),
        ollama_timeout_sec=_env_float("OLLAMA_TIMEOUT_SEC", 300.0),
        ollama_max_retries=_env_int("OLLAMA_MAX_RETRIES", 2),
        use_llm_process_bill=_env_bool("USE_LLM_PROCESS_BILL", True),
        ocr_debug=_env_bool("OCR_DEBUG", True),
        ocr_min_confidence=_env_float("OCR_MIN_CONFIDENCE", 0.3),
        ocr_preprocess_max_side=_env_int("OCR_PREPROCESS_MAX_SIDE", 1600),
        paddle_pdx_disable_model_source_check=_env_bool(
            "PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", True
        ),
        cors_allow_origins=_env_str("CORS_ALLOW_ORIGINS", "*"),
        log_level=_env_str("LOG_LEVEL", "INFO"),
        upload_folder=_env_str("UPLOAD_FOLDER", "uploads"),
        uvicorn_host=_env_str("UVICORN_HOST", "0.0.0.0"),
        uvicorn_port=_env_int("UVICORN_PORT", 8000),
    )


def cors_origins_list() -> list[str]:
    s = get_settings().cors_allow_origins.strip()
    if s == "*":
        return ["*"]
    return [p.strip() for p in s.split(",") if p.strip()]
