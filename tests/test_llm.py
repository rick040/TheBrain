from app.llm import get_embedding, llm


def test_llm_mock_mode_returns_something_stringlike():
    result = llm("hello", tier="default")
    assert "hello" in result


def test_llm_mock_mode_ignores_tier_choice():
    # Mock mode short-circuits before tier/provider config is even read —
    # confirms THEBRAIN_LLM_MOCK=1 works regardless of which tier is asked for.
    for tier in ("default", "strong", "escalate"):
        assert llm("x", tier=tier) is not None


def test_embedding_is_deterministic_and_right_length():
    v1 = get_embedding("the quick brown fox")
    v2 = get_embedding("the quick brown fox")
    v3 = get_embedding("something else entirely")
    assert len(v1) == 768
    assert v1 == v2
    assert v1 != v3


def test_embedding_values_are_bounded():
    v = get_embedding("bounded check")
    assert all(-1.0 <= x <= 1.0 for x in v)
