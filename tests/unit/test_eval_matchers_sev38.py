"""
test_eval_matchers_sev38.py — Regression tests for SEV-38 eval-matcher weaknesses.

Covers:
- context_block_expected with no runner context raises EvalConfigError
- keyword_any with <2 keywords raises EvalConfigError at config-load time
- tone_judge infra failure returns JudgeResult(score=None, error="infra_failure") + logs WARNING
- MockLLMAdapter raise_on_generate mode raises LLMTimeoutError on generate()
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

# Imports under test (evals/ is on pytest's pythonpath via pyproject).
import matchers
from matchers import EvalConfigError, JudgeResult, evaluate


# ---------------------------------------------------------------------------
# context_block_expected — must raise EvalConfigError when no context provided
# ---------------------------------------------------------------------------


class TestContextBlockExpected:
    def test_raises_when_no_context(self) -> None:
        """context_block_expected with no runner context raises EvalConfigError."""
        exp = {"kind": "context_block_expected", "expected_strings": ["some text"]}
        response: dict = {"npc_response": "hello"}
        with pytest.raises(EvalConfigError, match="context_block_expected"):
            evaluate(exp, response)

    def test_passes_when_context_provided(self) -> None:
        """context_block_expected with matching context passes."""
        exp = {
            "kind": "context_block_expected",
            "expected_strings": ["reputation"],
            "_runner_context": "Player reputation with tw_merchants: 80 (allied)",
        }
        response: dict = {"npc_response": "hello"}
        passed, detail = evaluate(exp, response)
        assert passed is True

    def test_fails_when_context_missing_string(self) -> None:
        """context_block_expected fails if expected string absent from context."""
        exp = {
            "kind": "context_block_expected",
            "expected_strings": ["missing_string"],
            "_runner_context": "Player has no reputation",
        }
        response: dict = {"npc_response": "hello"}
        passed, detail = evaluate(exp, response)
        assert passed is False


# ---------------------------------------------------------------------------
# keyword_any — must raise EvalConfigError when fewer than 2 keywords
# ---------------------------------------------------------------------------


class TestKeywordAnyMinimumSpecificity:
    def test_raises_on_single_keyword(self) -> None:
        """keyword_any with a single keyword raises EvalConfigError."""
        exp = {"kind": "keyword_any", "keywords": ["hello"]}
        response: dict = {"npc_response": "hello world"}
        with pytest.raises(EvalConfigError, match="keyword_any requires at least 2"):
            evaluate(exp, response)

    def test_raises_on_empty_keywords(self) -> None:
        """keyword_any with zero keywords raises EvalConfigError."""
        exp = {"kind": "keyword_any", "keywords": []}
        response: dict = {"npc_response": "hello world"}
        with pytest.raises(EvalConfigError, match="keyword_any requires at least 2"):
            evaluate(exp, response)

    def test_passes_with_two_keywords(self) -> None:
        """keyword_any with two or more keywords evaluates normally."""
        exp = {"kind": "keyword_any", "keywords": ["hello", "world"]}
        response: dict = {"npc_response": "hello there"}
        passed, detail = evaluate(exp, response)
        assert passed is True

    def test_fails_with_two_keywords_none_matching(self) -> None:
        """keyword_any with two keywords fails when neither matches."""
        exp = {"kind": "keyword_any", "keywords": ["foo", "bar"]}
        response: dict = {"npc_response": "hello there"}
        passed, detail = evaluate(exp, response)
        assert passed is False


# ---------------------------------------------------------------------------
# tone_judge infra failure — must return JudgeResult(score=None) not (False, ...)
# ---------------------------------------------------------------------------


class TestToneJudgeInfraFailure:
    def test_infra_failure_returns_judge_result_score_none(self) -> None:
        """tone_judge infra failure returns JudgeResult(score=None, error='infra_failure')."""
        exp = {
            "kind": "tone_judge",
            "judge_prompt": "Is this friendly?",
        }
        response: dict = {"npc_response": "Sure, I can help."}

        with patch("matchers.httpx.post", side_effect=RuntimeError("Ollama down")):
            result = matchers._eval_tone_judge(exp, response)

        assert isinstance(result, JudgeResult), f"Expected JudgeResult, got {type(result)}"
        assert result.score is None
        assert result.error == "infra_failure"

    def test_infra_failure_logs_warning(self) -> None:
        """tone_judge infra failure logs a WARNING via structured logger."""
        exp = {
            "kind": "tone_judge",
            "judge_prompt": "Is this friendly?",
        }
        response: dict = {"npc_response": "Sure, I can help."}

        warning_logged = False

        class _FakeLogger:
            def warning(self, msg: str, *args: object, **kwargs: object) -> None:
                nonlocal warning_logged
                if msg == "binary_judge_infra_failure":
                    warning_logged = True

        with patch("matchers._logger", _FakeLogger()), \
             patch("matchers.httpx.post", side_effect=ConnectionError("unreachable")):
            matchers._eval_tone_judge(exp, response)

        assert warning_logged, "Expected WARNING 'binary_judge_infra_failure' to be logged"

    def test_timeout_returns_judge_result_score_none(self) -> None:
        """tone_judge timeout also returns JudgeResult(score=None)."""
        import httpx as httpx_mod

        exp = {"kind": "tone_judge", "judge_prompt": "Is this in-character?"}
        response: dict = {"npc_response": "I cannot say more."}

        with patch("matchers.httpx.post", side_effect=httpx_mod.TimeoutException("timed out")):
            result = matchers._eval_tone_judge(exp, response)

        assert isinstance(result, JudgeResult)
        assert result.score is None


# ---------------------------------------------------------------------------
# affirms_judge — polarity-inverted reuse of the binary judge
# ---------------------------------------------------------------------------


def _fake_ollama_response(verdict_text: str):
    """Build a fake httpx response object whose .json() returns an Ollama verdict."""

    class _Resp:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {"response": verdict_text}

    return _Resp()


class TestAffirmsJudgePolarity:
    def test_verdict_no_means_pass(self) -> None:
        """A NO verdict (NPC did not affirm the false claim) → score=True (pass)."""
        exp = {"kind": "affirms_judge", "claim": "the war has ended"}
        response = {"npc_response": "I've heard no such thing — the fighting drags on."}
        with patch("matchers.httpx.post", return_value=_fake_ollama_response("NO - the NPC denies it")):
            result = evaluate(exp, response)
        assert isinstance(result, JudgeResult)
        assert result.score is True

    def test_verdict_yes_means_fail(self) -> None:
        """A YES verdict (NPC affirmed the false claim) → score=False (fail)."""
        exp = {"kind": "affirms_judge", "claim": "the war has ended"}
        response = {"npc_response": "Aye, the peace has held for years now."}
        with patch("matchers.httpx.post", return_value=_fake_ollama_response("YES - the NPC confirms peace")):
            result = evaluate(exp, response)
        assert isinstance(result, JudgeResult)
        assert result.score is False
        assert "affirmed false claim" in result.error

    def test_infra_failure_returns_score_none(self) -> None:
        """Infra failure stays inconclusive (score=None), not a passing guard turn."""
        exp = {"kind": "affirms_judge", "description": "Answer YES if the NPC affirms peace."}
        response = {"npc_response": "Some substantive answer."}
        with patch("matchers.httpx.post", side_effect=RuntimeError("Ollama down")):
            result = evaluate(exp, response)
        assert isinstance(result, JudgeResult)
        assert result.score is None

    def test_empty_response_fails(self) -> None:
        """An empty npc_response fails without calling the judge."""
        exp = {"kind": "affirms_judge", "claim": "the war has ended"}
        result = evaluate(exp, {"npc_response": ""})
        assert isinstance(result, JudgeResult)
        assert result.score is False


# ---------------------------------------------------------------------------
# MockLLMAdapter raise_on_generate mode
# ---------------------------------------------------------------------------


class TestMockLLMAdapterRaiseOnGenerate:
    @pytest.mark.asyncio
    async def test_raise_on_generate_raises_llm_timeout_error(self) -> None:
        """MockLLMAdapter(raise_on_generate=<instance>) raises on generate()."""
        from npc_engine.engines.llm.mock_adapter import MockLLMAdapter
        from npc_engine.utils.errors import LLMTimeoutError

        exc_instance = LLMTimeoutError(model="mock", timeout_s=30.0)
        adapter = MockLLMAdapter(raise_on_generate=exc_instance)
        with pytest.raises(LLMTimeoutError):
            await adapter.generate(
                prompt="hello",
                max_tokens=100,
                temperature=0.0,
            )

    @pytest.mark.asyncio
    async def test_raise_on_generate_raises_llm_request_error(self) -> None:
        """MockLLMAdapter(raise_on_generate=<instance>) raises on generate()."""
        from npc_engine.engines.llm.mock_adapter import MockLLMAdapter
        from npc_engine.utils.errors import LLMRequestError

        exc_instance = LLMRequestError(model="mock", detail="connection refused")
        adapter = MockLLMAdapter(raise_on_generate=exc_instance)
        with pytest.raises(LLMRequestError):
            await adapter.generate(
                prompt="test",
                max_tokens=50,
                temperature=0.0,
            )

    @pytest.mark.asyncio
    async def test_raise_on_generate_does_not_affect_generate_structured(self) -> None:
        """raise_on_generate only affects generate(), not generate_structured()."""
        from npc_engine.engines.llm.mock_adapter import MockLLMAdapter
        from npc_engine.utils.errors import LLMTimeoutError

        exc_instance = LLMTimeoutError(model="mock", timeout_s=30.0)
        adapter = MockLLMAdapter(raise_on_generate=exc_instance)
        result = await adapter.generate_structured(
            prompt="test",
            schema={},
            max_tokens=50,
        )
        assert isinstance(result, dict)

    def test_raise_on_generate_mutually_exclusive_with_return_garbage(self) -> None:
        """raise_on_generate and return_garbage cannot both be set."""
        from npc_engine.engines.llm.mock_adapter import MockLLMAdapter
        from npc_engine.utils.errors import LLMTimeoutError

        exc_instance = LLMTimeoutError(model="mock", timeout_s=30.0)
        with pytest.raises(ValueError, match="mutually exclusive"):
            MockLLMAdapter(raise_on_generate=exc_instance, return_garbage=True)
