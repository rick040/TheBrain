"""Shared config loading: vault/_system/config.yaml (non-secret settings)
+ environment variables (secrets, from a local .env — see .env.example).
Never put a secret in config.yaml; it's committed to git.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_VAULT_CONFIG = REPO_ROOT / "vault" / "_system" / "config.yaml"

_dotenv_loaded = False


def _load_dotenv_once() -> None:
    """Minimal .env loader (KEY=VALUE per line) so we don't force a
    python-dotenv dependency for something this small. No-op if .env
    doesn't exist or was already loaded."""
    global _dotenv_loaded
    if _dotenv_loaded:
        return
    _dotenv_loaded = True
    env_path = REPO_ROOT / ".env"
    if not env_path.is_file():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        os.environ.setdefault(key, value)


def load_vault_config(path: Path | None = None) -> dict[str, Any]:
    """Read vault/_system/config.yaml — llm tiers, coach schedule,
    thresholds, locale. Non-secret; safe to commit (it already is)."""
    config_path = path or DEFAULT_VAULT_CONFIG
    with open(config_path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_env(name: str, *, required: bool = False, default: str | None = None) -> str | None:
    """Read a secret/setting from the environment, loading .env first."""
    _load_dotenv_once()
    value = os.environ.get(name, default)
    if required and not value:
        raise RuntimeError(
            f"missing required environment variable '{name}' — "
            f"see .env.example, copy it to .env, and fill it in."
        )
    return value
