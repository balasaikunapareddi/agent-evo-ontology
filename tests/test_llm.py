"""Tests for the LiteLLM backend's pacing and 429 retry.

The stub path never touches LiteLLM, so these tests fake
litellm.completion and time.sleep — no key, no network, no waiting.
"""
import litellm
from litellm.exceptions import RateLimitError

from agent_evo_ontology.llm import LiteLLMBackend


class _Choice:
    def __init__(self, content):
        self.message = type("M", (), {"content": content})()


class _Response:
    def __init__(self, content):
        self.choices = [_Choice(content)]


def _rate_limit_error():
    return RateLimitError("429", "gemini", "gemini/gemini-3.5-flash-lite")


def test_generate_retries_rate_limit_then_succeeds(monkeypatch):
    monkeypatch.setenv("LLM_MIN_INTERVAL_S", "0")
    calls = {"n": 0}

    def fake_completion(**kwargs):
        calls["n"] += 1
        if calls["n"] <= 2:
            raise _rate_limit_error()
        return _Response("SELECT 1")

    monkeypatch.setattr(litellm, "completion", fake_completion)
    sleeps: list[float] = []
    monkeypatch.setattr("agent_evo_ontology.llm.time.sleep",
                        lambda s: sleeps.append(s))
    backend = LiteLLMBackend(model="gemini/gemini-3.5-flash-lite")
    assert backend.generate("hi") == "SELECT 1"
    assert calls["n"] == 3
    # Two 429s -> two 60 s waits before the succeeding call.
    assert sleeps == [60.0, 60.0]


def test_generate_gives_up_after_retries(monkeypatch):
    monkeypatch.setenv("LLM_MIN_INTERVAL_S", "0")
    monkeypatch.setattr(litellm, "completion",
                        lambda **kwargs: (_ for _ in ()).throw(
                            _rate_limit_error()))
    monkeypatch.setattr("agent_evo_ontology.llm.time.sleep", lambda s: None)
    backend = LiteLLMBackend(model="gemini/gemini-3.5-flash-lite")
    try:
        backend.generate("hi")
    except RateLimitError:
        return
    raise AssertionError("expected RateLimitError after retries exhausted")


def test_generate_paces_calls(monkeypatch):
    monkeypatch.setenv("LLM_MIN_INTERVAL_S", "4.5")
    monkeypatch.setattr(litellm, "completion",
                        lambda **kwargs: _Response("SELECT 1"))
    sleeps: list[float] = []
    monkeypatch.setattr("agent_evo_ontology.llm.time.sleep",
                        lambda s: sleeps.append(s))
    clock = {"t": 1000.0}
    monkeypatch.setattr("agent_evo_ontology.llm.time.monotonic",
                        lambda: clock["t"])
    backend = LiteLLMBackend(model="gemini/gemini-3.5-flash-lite")
    backend.generate("one")  # first call: no prior call, no wait
    assert sleeps == []
    clock["t"] = 1001.0  # 1 s later: second call must wait 3.5 s
    backend.generate("two")
    assert sleeps == [4.5 - 1.0]
