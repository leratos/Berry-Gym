import json
import runpy
import types
from unittest.mock import MagicMock, patch

import pytest

from ai_coach.llm_client import LLMClient


class TestLLMClientInitAndAvailability:
    def test_init_sets_ollama_available_when_check_passes(self):
        with patch.object(LLMClient, "_check_ollama_available", return_value=None):
            client = LLMClient(use_openrouter=False)

        assert client.ollama_available is True

    def test_init_raises_when_no_fallback_and_ollama_unavailable(self):
        with patch.object(LLMClient, "_check_ollama_available", side_effect=Exception("down")):
            with pytest.raises(Exception, match="down"):
                LLMClient(use_openrouter=False, fallback_to_openrouter=False)

    def test_init_uses_fallback_when_ollama_unavailable(self):
        with patch.object(LLMClient, "_check_ollama_available", side_effect=Exception("down")):
            client = LLMClient(use_openrouter=False, fallback_to_openrouter=True)

        assert client.ollama_available is False

    def test_check_ollama_available_missing_model_raises(self):
        with patch("ai_coach.llm_client.ollama.list", return_value={"models": [{"name": "other"}]}):
            client = LLMClient(use_openrouter=True)
            with pytest.raises(Exception, match="nicht erreichbar"):
                client._check_ollama_available()

    def test_check_ollama_available_wraps_list_error(self):
        with patch("ai_coach.llm_client.ollama.list", side_effect=RuntimeError("boom")):
            client = LLMClient(use_openrouter=True)
            with pytest.raises(Exception, match="Ollama nicht erreichbar"):
                client._check_ollama_available()


class TestOpenRouterClientInit:
    def test_get_openrouter_client_success_and_cache(self):
        fake_openai_module = types.SimpleNamespace(OpenAI=MagicMock(return_value="client-instance"))

        with (
            patch.dict("sys.modules", {"openai": fake_openai_module}),
            patch("ai_coach.secrets_manager.get_openrouter_key", return_value="sk-test"),
        ):
            client = LLMClient(use_openrouter=True)
            first = client._get_openrouter_client()
            second = client._get_openrouter_client()

        assert first == "client-instance"
        assert second == "client-instance"

    def test_get_openrouter_client_missing_key_raises(self):
        fake_openai_module = types.SimpleNamespace(OpenAI=MagicMock())

        with (
            patch.dict("sys.modules", {"openai": fake_openai_module}),
            patch("ai_coach.secrets_manager.get_openrouter_key", return_value=None),
        ):
            client = LLMClient(use_openrouter=True)
            with pytest.raises(Exception, match="OPENROUTER_API_KEY nicht gefunden"):
                client._get_openrouter_client()


class TestGenerateTrainingPlanStrategy:
    def test_use_openrouter_strategy(self):
        client = LLMClient(use_openrouter=True)
        with patch.object(
            client, "_generate_with_openrouter", return_value={"ok": True}
        ) as mock_or:
            result = client.generate_training_plan(messages=[])

        assert result == {"ok": True}
        mock_or.assert_called_once()

    def test_ollama_then_fallback_to_openrouter(self):
        client = LLMClient(use_openrouter=True)
        client.use_openrouter = False
        client.ollama_available = True
        client.fallback_to_openrouter = True

        with (
            patch.object(client, "_generate_with_ollama", side_effect=RuntimeError("ollama fail")),
            patch.object(
                client, "_generate_with_openrouter", return_value={"ok": "fallback"}
            ) as mock_or,
        ):
            result = client.generate_training_plan(messages=[])

        assert result == {"ok": "fallback"}
        mock_or.assert_called_once()

    def test_no_llm_available_raises(self):
        client = LLMClient(use_openrouter=True)
        client.use_openrouter = False
        client.ollama_available = False
        client.fallback_to_openrouter = False

        with pytest.raises(Exception, match="Kein LLM verfügbar"):
            client.generate_training_plan(messages=[])


class TestOllamaAndOpenRouterPaths:
    def test_generate_with_ollama_success(self):
        client = LLMClient(use_openrouter=True)

        with (
            patch(
                "ai_coach.llm_client.ollama.chat",
                return_value={
                    "message": {"content": '{"plan_name": "Test", "sessions": []}'},
                    "total_duration": 1_000_000_000,
                    "eval_count": 123,
                },
            ),
            patch.object(
                client, "_extract_json", return_value={"plan_name": "Test", "sessions": []}
            ),
        ):
            result = client._generate_with_ollama(messages=[], max_tokens=1000, timeout=10)

        assert result["response"]["plan_name"] == "Test"
        assert result["tokens"] == 123
        assert result["cost"] == 0.0

    def test_generate_with_openrouter_success(self):
        usage = types.SimpleNamespace(total_tokens=1000, prompt_tokens=700, completion_tokens=300)
        msg = types.SimpleNamespace(content='{"plan_name":"X","sessions":[]}')
        choice = types.SimpleNamespace(message=msg)
        response = types.SimpleNamespace(choices=[choice], usage=usage)

        fake_client = MagicMock()
        fake_client.chat.completions.create.return_value = response

        client = LLMClient(use_openrouter=True)
        with (
            patch.object(client, "_get_openrouter_client", return_value=fake_client),
            patch.object(client, "_extract_json", return_value={"plan_name": "X", "sessions": []}),
        ):
            result = client._generate_with_openrouter(messages=[], max_tokens=1500, timeout=20)

        assert result["model"]
        assert result["tokens"] == 1000
        assert "usage" in result
        assert result["response"]["plan_name"] == "X"


class TestExtractJsonAndValidatePlan:
    def test_extract_json_handles_markdown_and_repairs_range(self):
        client = LLMClient(use_openrouter=True)
        content = """```json
{
  \"plan_name\": \"A\",
  \"sessions\": [{\"day_name\":\"D\",\"exercises\":[{\"sets\":3,\"reps\":8-12,\"order\":1}]}],
}
```"""
        parsed = client._extract_json(content)

        assert parsed["plan_name"] == "A"
        assert parsed["sessions"][0]["exercises"][0]["reps"] == "8-12"

    def test_extract_json_uses_json_repair_fallback(self):
        client = LLMClient(use_openrouter=True)

        def _fake_loads(_):
            raise json.JSONDecodeError("bad", "{}", 1)

        fake_json_repair = types.SimpleNamespace(
            repair_json=lambda *_args, **_kwargs: {"plan_name": "R", "sessions": []}
        )

        with (
            patch("ai_coach.llm_client.json.loads", side_effect=_fake_loads),
            patch.dict("sys.modules", {"json_repair": fake_json_repair}),
        ):
            parsed = client._extract_json('{"bad": true}')

        assert parsed["plan_name"] == "R"

    def test_extract_json_empty_raises(self):
        client = LLMClient(use_openrouter=True)
        with pytest.raises(ValueError, match="Leere LLM Response"):
            client._extract_json("   ")

    def test_validate_plan_invalid_and_valid_cases(self):
        client = LLMClient(use_openrouter=True)

        valid, errors = client.validate_plan(plan_json="no-dict", available_exercises=[])
        assert valid is False
        assert errors

        plan = {
            "plan_name": "OK",
            "sessions": [
                {
                    "day_name": "A",
                    "exercises": [
                        {"exercise_name": "Bankdrücken", "sets": 3, "reps": "8-10", "order": 1}
                    ],
                }
            ],
        }
        valid2, errors2 = client.validate_plan(plan_json=plan, available_exercises=["Bankdrücken"])
        assert valid2 is True
        assert errors2 == []


class TestLlmClientMainGuard:
    def test_module_main_guard_runs(self):
        with (
            patch(
                "ai_coach.llm_client.ollama.list",
                return_value={"models": [{"name": "llama3.1:8b"}]},
            ),
            patch(
                "ai_coach.llm_client.ollama.chat",
                return_value={
                    "message": {"content": '{"plan_name":"T","sessions":[]}'},
                    "total_duration": 1_000_000,
                    "eval_count": 10,
                },
            ),
        ):
            result_globals = runpy.run_module("ai_coach.llm_client", run_name="__main__")

        assert "LLMClient" in result_globals
