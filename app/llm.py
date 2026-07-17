"""The llm() abstraction — docs/03-engineering-build-spec.md §7.5.

    tier="default"  -> Haiku   : normalization, tagging, coach messages, routine metabolism
    tier="strong"   -> Sonnet  : evaluator deep report, gap-review synthesis
    tier="escalate" -> Opus    : on-demand only, e.g. the metabolism pass that
                                 revises self/current traits (see docs/00-PLAN.md)

Provider is config-driven (vault/_system/config.yaml `llm:` block) so that
adding a local Ollama provider later is a config edit, not a caller change
(spec DoD for this module). Set THEBRAIN_LLM_MOCK=1 to force the mock
provider — used by tests and anywhere you don't want to spend API tokens
or need network.
"""
from __future__ import annotations

import hashlib
import os
from typing import Literal

from app.common.config import get_env, load_vault_config

Tier = Literal["default", "strong", "escalate"]


class MockResponse(str):
    """A str subclass so mock responses work anywhere a real string
    response would, while being visibly identifiable in tests/logs."""


def _mock_call(prompt: str, *, system: str | None, max_tokens: int) -> str:
    return MockResponse(f"[mock:{max_tokens}] {prompt[:200]}")


def _anthropic_call(prompt: str, *, system: str | None, max_tokens: int, model: str) -> str:
    # Imported lazily: the `anthropic` package isn't needed for mock-mode
    # tests or for code paths that never call a real tier.
    import anthropic

    client = anthropic.Anthropic(api_key=get_env("ANTHROPIC_API_KEY", required=True))
    kwargs: dict = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }
    if system:
        kwargs["system"] = system
    response = client.messages.create(**kwargs)
    return "".join(block.text for block in response.content if block.type == "text")


def _ollama_call(prompt: str, *, system: str | None, max_tokens: int, model: str) -> str:
    # Stub for the local-NAS end state (docs/00-PLAN.md) — untested until
    # there's an Ollama host to point at. Wiring is intentionally the same
    # shape as _anthropic_call so swapping tiers over to it is a config
    # edit, per the module's DoD.
    import requests

    host = get_env("OLLAMA_HOST", default="http://localhost:11434")
    full_prompt = f"{system}\n\n{prompt}" if system else prompt
    resp = requests.post(
        f"{host}/api/generate",
        json={"model": model, "prompt": full_prompt, "stream": False},
        timeout=120,
    )
    resp.raise_for_status()
    return resp.json()["response"]


def llm(
    prompt: str,
    *,
    tier: Tier = "default",
    system: str | None = None,
    max_tokens: int = 1024,
) -> str:
    if os.environ.get("THEBRAIN_LLM_MOCK") == "1":
        return _mock_call(prompt, system=system, max_tokens=max_tokens)

    config = load_vault_config()
    tier_config = config["llm"][tier]
    provider = tier_config["provider"]
    model = tier_config["model"]

    if provider == "anthropic":
        return _anthropic_call(prompt, system=system, max_tokens=max_tokens, model=model)
    if provider == "ollama":
        return _ollama_call(prompt, system=system, max_tokens=max_tokens, model=model)
    if provider == "mock":
        return _mock_call(prompt, system=system, max_tokens=max_tokens)
    raise ValueError(f"unknown llm provider '{provider}' for tier '{tier}'")


def _mock_embedding(text: str, dim: int) -> list[float]:
    """Deterministic, non-semantic pseudo-embedding for tests/CI — a hash
    stretched to `dim` floats in [-1, 1]. Never mistake this for a real
    embedding; it does not encode meaning, only reproducibility."""
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    values = []
    i = 0
    while len(values) < dim:
        byte = digest[i % len(digest)]
        values.append((byte / 127.5) - 1.0)
        i += 1
    return values[:dim]


def get_embedding(text: str) -> list[float]:
    """Embedding provider selection — see vault/_system/config.yaml
    `embeddings:` block. Defaults to the mock embedder until a worker
    host with Ollama exists (docs/00-PLAN.md); switching is a config
    edit, matching llm()'s own swap-provider guarantee."""
    if os.environ.get("THEBRAIN_LLM_MOCK") == "1":
        return _mock_embedding(text, 768)

    config = load_vault_config()
    emb_config = config.get("embeddings", {"provider": "mock", "dim": 768})
    provider = emb_config.get("provider", "mock")
    dim = emb_config.get("dim", 768)

    if provider == "mock":
        return _mock_embedding(text, dim)
    if provider == "ollama":
        import requests

        host = get_env("OLLAMA_HOST", default="http://localhost:11434")
        resp = requests.post(
            f"{host}/api/embeddings",
            json={"model": emb_config.get("model", "nomic-embed-text"), "prompt": text},
            timeout=60,
        )
        resp.raise_for_status()
        return resp.json()["embedding"]
    raise ValueError(f"unknown embedding provider '{provider}'")
