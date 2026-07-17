import os

import pytest


@pytest.fixture(autouse=True, scope="session")
def _mock_llm():
    """Every test runs against app/llm.py's mock provider — no network,
    no API key, no cost. See docs/03-engineering-build-spec.md §7.5 DoD:
    "a mock provider lets all jobs run offline in tests"."""
    os.environ["THEBRAIN_LLM_MOCK"] = "1"
