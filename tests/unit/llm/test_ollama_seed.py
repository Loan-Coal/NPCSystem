"""
test_ollama_seed.py - Deterministic seed forwarding for the Ollama adapter (EVAL-P20.0).

Does NOT: call live LLM services, or assert anything about real model determinism —
Ollama's seed is not a bit-identical guarantee across quantisation or driver versions,
so the >=95% reproduction claim is a measured live gate (scripts/seed_reproduction_probe.py),
never a unit test.

Dependencies injected: Monkeypatched HTTP client whose reply text is a function of
options["seed"], so an implementation that drops the seed cannot pass.

Roadmap note: EVAL-P20.0 names this file as tests/unit/engines/llm/test_ollama_seed.py.
That directory does not exist and every LLM adapter test already lives in tests/unit/llm/;
the anchor test name is unchanged. See DEC-176.
"""

import pytest

from npc_engine.engines.llm.ollama_adapter import OllamaAdapter


_SEED = 4242
_OTHER_SEED = 99


class _SeedEchoResponse:
    """Fake HTTP response whose payload was derived from the request seed."""

    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self):
        return self._payload


class _SeedEchoStreamResponse:
    """Streaming response yielding one token derived from the request seed."""

    def __init__(self, seed):
        self._seed = seed

    def raise_for_status(self) -> None:
        return None

    async def aiter_lines(self):
        yield '{"response": "reply-for-seed-%s"}' % self._seed

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _SeedEchoOllamaClient:
    """Records the last payload and echoes options['seed'] back in the reply text."""

    def __init__(self, timeout: float):
        self.last_payload: dict = {}

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def post(self, url: str, json: dict):
        self.last_payload = json
        seed = json["options"].get("seed")
        if "format" in json:
            return _SeedEchoResponse({"response": '{"text": "reply-for-seed-%s"}' % seed})
        return _SeedEchoResponse({"response": f"reply-for-seed-{seed}"})

    def stream(self, method: str, url: str, json: dict):
        self.last_payload = json
        return _SeedEchoStreamResponse(json["options"].get("seed"))


_seed_echo_instance: _SeedEchoOllamaClient | None = None


def _seed_echo_factory(timeout: float) -> _SeedEchoOllamaClient:
    global _seed_echo_instance
    _seed_echo_instance = _SeedEchoOllamaClient(timeout)
    return _seed_echo_instance


def _adapter(monkeypatch) -> OllamaAdapter:
    monkeypatch.setattr("npc_engine.engines.llm.ollama_adapter.httpx.AsyncClient", _seed_echo_factory)
    return OllamaAdapter(base_url="http://fake", model_name="mixtral:8x7b", timeout_seconds=1.0)


@pytest.mark.asyncio
async def test_same_seed_reproduces_identical_text(monkeypatch) -> None:
    adapter = _adapter(monkeypatch)

    text_a = await adapter.generate(prompt="p", max_tokens=10, temperature=0.15, seed=_SEED)
    assert _seed_echo_instance is not None
    assert _seed_echo_instance.last_payload["options"]["seed"] == _SEED

    text_b = await adapter.generate(prompt="p", max_tokens=10, temperature=0.15, seed=_SEED)
    other = await adapter.generate(prompt="p", max_tokens=10, temperature=0.15, seed=_OTHER_SEED)

    assert text_a != ""
    assert text_a == text_b
    assert other != text_a


@pytest.mark.asyncio
async def test_ollama_generate_omits_seed_when_none(monkeypatch) -> None:
    adapter = _adapter(monkeypatch)
    await adapter.generate(prompt="p", max_tokens=10, temperature=0.15)

    assert _seed_echo_instance is not None
    assert "seed" not in _seed_echo_instance.last_payload["options"]


@pytest.mark.asyncio
async def test_ollama_generate_structured_forwards_seed(monkeypatch) -> None:
    adapter = _adapter(monkeypatch)
    await adapter.generate_structured(prompt="p", schema={}, max_tokens=10, seed=_SEED)

    assert _seed_echo_instance is not None
    assert _seed_echo_instance.last_payload["options"]["seed"] == _SEED


@pytest.mark.asyncio
async def test_ollama_generate_structured_omits_seed_when_none(monkeypatch) -> None:
    adapter = _adapter(monkeypatch)
    await adapter.generate_structured(prompt="p", schema={}, max_tokens=10)

    assert _seed_echo_instance is not None
    assert "seed" not in _seed_echo_instance.last_payload["options"]


@pytest.mark.asyncio
async def test_ollama_stream_forwards_seed(monkeypatch) -> None:
    adapter = _adapter(monkeypatch)

    chunks = []
    async for token in adapter.stream(prompt="p", max_tokens=10, temperature=0.15, seed=_SEED):
        chunks.append(token)

    assert _seed_echo_instance is not None
    assert _seed_echo_instance.last_payload["options"]["seed"] == _SEED
    assert chunks == [f"reply-for-seed-{_SEED}"]


@pytest.mark.asyncio
async def test_ollama_stream_omits_seed_when_none(monkeypatch) -> None:
    adapter = _adapter(monkeypatch)

    async for _ in adapter.stream(prompt="p", max_tokens=10, temperature=0.15):
        pass

    assert _seed_echo_instance is not None
    assert "seed" not in _seed_echo_instance.last_payload["options"]
