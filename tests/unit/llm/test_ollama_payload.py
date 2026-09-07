"""
test_ollama_payload.py - Request shaping for the Ollama backend, tested without HTTP.

Why this exists: the three OllamaAdapter generation methods each hand-built the same
options and payload dicts, so every assertion about request shape had to go through a
monkeypatched httpx client and an async test. Extracting the shaping into pure functions
makes it directly testable, and gives keep_alive one place to live instead of three.

Does NOT: call a live Ollama backend, construct an adapter, or read Settings.

Dependencies injected: none - every value is passed per call.
"""

from __future__ import annotations

from npc_engine.engines.llm.ollama_payload import build_ollama_options, build_ollama_payload

_NUM_CTX = 12288


def test_options_carry_num_predict_temperature_and_num_ctx() -> None:
    """The three mandatory sampling options are always present."""
    options = build_ollama_options(max_tokens=512, temperature=0.15, num_ctx=_NUM_CTX)

    assert options["num_predict"] == 512
    assert options["temperature"] == 0.15
    assert options["num_ctx"] == _NUM_CTX


def test_options_omit_optional_keys_when_none() -> None:
    """Absent optional sampling controls must not be sent as nulls."""
    options = build_ollama_options(max_tokens=64, temperature=0.5, num_ctx=_NUM_CTX)

    assert "top_p" not in options
    assert "stop" not in options
    assert "seed" not in options


def test_options_include_optional_keys_when_given() -> None:
    """stop_sequences maps to the backend's `stop` key, not `stop_sequences`."""
    options = build_ollama_options(
        max_tokens=64,
        temperature=0.5,
        num_ctx=_NUM_CTX,
        top_p=0.95,
        stop_sequences=["STOP"],
        seed=20260814,
    )

    assert options["top_p"] == 0.95
    assert options["stop"] == ["STOP"]
    assert options["seed"] == 20260814


def test_payload_carries_model_prompt_and_options() -> None:
    """The happy path forwards identity, prompt and the prepared options dict."""
    options = build_ollama_options(max_tokens=64, temperature=0.5, num_ctx=_NUM_CTX)
    payload = build_ollama_payload(
        model="qwen2.5:7b", prompt="hello", options=options, keep_alive="30m"
    )

    assert payload["model"] == "qwen2.5:7b"
    assert payload["prompt"] == "hello"
    assert payload["options"] is options
    assert payload["stream"] is False


def test_payload_carries_keep_alive_as_a_top_level_field() -> None:
    """keep_alive is a top-level Ollama field; inside `options` it is silently ignored."""
    options = build_ollama_options(max_tokens=64, temperature=0.5, num_ctx=_NUM_CTX)
    payload = build_ollama_payload(
        model="qwen2.5:7b", prompt="hello", options=options, keep_alive="30m"
    )

    assert payload["keep_alive"] == "30m"
    assert "keep_alive" not in payload["options"]


def test_payload_omits_format_when_no_schema_is_given() -> None:
    """A plain-text request must not carry an empty grammar."""
    options = build_ollama_options(max_tokens=64, temperature=0.5, num_ctx=_NUM_CTX)
    payload = build_ollama_payload(
        model="qwen2.5:7b", prompt="hello", options=options, keep_alive="30m"
    )

    assert "format" not in payload


def test_payload_carries_the_schema_as_format() -> None:
    """Structured requests pass the JSON schema through Ollama's `format` field."""
    schema = {"type": "object"}
    options = build_ollama_options(max_tokens=64, temperature=0.1, num_ctx=_NUM_CTX)
    payload = build_ollama_payload(
        model="qwen2.5:7b", prompt="hello", options=options, keep_alive="30m", schema=schema
    )

    assert payload["format"] is schema


def test_payload_omits_system_when_none() -> None:
    """An absent system prompt must not be sent as a null."""
    options = build_ollama_options(max_tokens=64, temperature=0.5, num_ctx=_NUM_CTX)
    payload = build_ollama_payload(
        model="qwen2.5:7b", prompt="hello", options=options, keep_alive="30m"
    )

    assert "system" not in payload


def test_payload_carries_system_when_given() -> None:
    """The system channel is forwarded verbatim when present."""
    options = build_ollama_options(max_tokens=64, temperature=0.5, num_ctx=_NUM_CTX)
    payload = build_ollama_payload(
        model="qwen2.5:7b",
        prompt="hello",
        options=options,
        keep_alive="30m",
        system="you are an NPC",
    )

    assert payload["system"] == "you are an NPC"


def test_payload_marks_streaming_requests() -> None:
    """The streaming path differs from generate only by this flag."""
    options = build_ollama_options(max_tokens=64, temperature=0.5, num_ctx=_NUM_CTX)
    payload = build_ollama_payload(
        model="qwen2.5:7b", prompt="hello", options=options, keep_alive="30m", stream=True
    )

    assert payload["stream"] is True
