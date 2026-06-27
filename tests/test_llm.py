from __future__ import annotations

import pytest
from pydantic import BaseModel

from src.llm.base import LLMProvider
from src.llm.engine import LLMEngine, LLMEngineError
from src.llm.ollama import OllamaError, OllamaProvider
from src.prompts.loader import PromptLoader


class TestLLMProvider:
    def test_cannot_instantiate_abstract_provider(self):
        with pytest.raises(TypeError):
            LLMProvider()  # type: ignore[abstract]


class TestOllamaProvider:
    @pytest.mark.asyncio
    async def test_generate_success(self, respx_mock):
        respx_mock.post("http://localhost:11434/api/generate").respond(
            json={"response": "Hello from Ollama"},
        )
        provider = OllamaProvider(model="gemma3", base_url="http://localhost:11434", timeout=30)
        result = await provider.generate("Say hello")
        assert result == "Hello from Ollama"

    @pytest.mark.asyncio
    async def test_generate_connection_error(self):
        provider = OllamaProvider(model="gemma3", base_url="http://localhost:19999", timeout=1)
        with pytest.raises(OllamaError, match="Failed to reach Ollama"):
            await provider.generate("test")

    @pytest.mark.asyncio
    async def test_generate_http_error(self, respx_mock):
        respx_mock.post("http://localhost:11434/api/generate").respond(
            status_code=500, text="Internal error"
        )
        provider = OllamaProvider(model="gemma3", base_url="http://localhost:11434", timeout=30)
        with pytest.raises(OllamaError, match="Ollama returned error 500"):
            await provider.generate("test")

    @pytest.mark.asyncio
    async def test_generate_empty_response(self, respx_mock):
        respx_mock.post("http://localhost:11434/api/generate").respond(json={"response": ""})
        provider = OllamaProvider(model="gemma3", base_url="http://localhost:11434", timeout=30)
        with pytest.raises(OllamaError, match="empty response"):
            await provider.generate("test")

    @pytest.mark.asyncio
    async def test_provider_uses_configured_values(self):
        provider = OllamaProvider(model="qwen2.5", base_url="http://custom:8080", timeout=120)
        assert provider._model == "qwen2.5"
        assert provider._base_url == "http://custom:8080"
        assert provider._timeout == 120

    @pytest.mark.asyncio
    async def test_generate_non_json_response(self, respx_mock):
        respx_mock.post("http://localhost:11434/api/generate").respond(
            text="not json",
            headers={"content-type": "text/plain"},
        )
        provider = OllamaProvider(model="gemma3", base_url="http://localhost:11434", timeout=30)
        with pytest.raises(OllamaError, match="non-JSON"):
            await provider.generate("test")


class MockProvider(LLMProvider):
    def __init__(self, responses: list[str] | None = None):
        self.call_count = 0
        self._responses = responses or ["mock response"]

    async def generate(self, prompt: str) -> str:
        self.call_count += 1
        if self.call_count <= len(self._responses):
            return self._responses[self.call_count - 1]
        return self._responses[-1]


class ScoreModel(BaseModel):
    score: int
    label: str


class TestLLMEngine:
    def test_engine_uses_prompt_loader(self):
        provider = MockProvider()
        loader = PromptLoader()
        engine = LLMEngine(provider, loader)
        assert engine._provider is provider
        assert engine._prompt_loader is loader

    @pytest.mark.asyncio
    async def test_generate_text_renders_and_returns(self):
        provider = MockProvider(["Hello World"])
        loader = PromptLoader()
        engine = LLMEngine(provider, loader)

        result = await engine.generate_text("rewrite", current_answer="test", company="ACME")

        assert result == "Hello World"
        assert provider.call_count == 1

    @pytest.mark.asyncio
    async def test_generate_text_strips_whitespace(self):
        provider = MockProvider(["  padded result  "])
        loader = PromptLoader()
        engine = LLMEngine(provider, loader)

        result = await engine.generate_text("rewrite", current_answer="test", company="ACME")

        assert result == "padded result"

    @pytest.mark.asyncio
    async def test_generate_structured_parses_json(self):
        provider = MockProvider(['{"score": 85, "label": "good match"}'])
        loader = PromptLoader()
        engine = LLMEngine(provider, loader)

        result = await engine.generate_structured(
            "job_matching",
            ScoreModel,
            company="ACME",
            title="Engineer",
            location="Remote",
            employment_type="full-time",
            description="Build things",
            name="Jane",
            profile_title="Developer",
            skills="Python",
            experience="5 years",
            education="BS",
        )

        assert isinstance(result, ScoreModel)
        assert result.score == 85
        assert result.label == "good match"

    @pytest.mark.asyncio
    async def test_generate_structured_retries_on_bad_json(self):
        provider = MockProvider(["not json", '{"score": 90, "label": "great"}'])
        loader = PromptLoader()
        engine = LLMEngine(provider, loader, max_retries=2)

        result = await engine.generate_structured(
            "job_matching",
            ScoreModel,
            company="ACME",
            title="Engineer",
            location="Remote",
            employment_type="full-time",
            description="Build things",
            name="Jane",
            profile_title="Developer",
            skills="Python",
            experience="5 years",
            education="BS",
        )

        assert isinstance(result, ScoreModel)
        assert result.score == 90
        assert provider.call_count == 2

    @pytest.mark.asyncio
    async def test_generate_structured_retries_on_validation_error(self):
        provider = MockProvider([
            '{"score": "bad", "label": "nope"}',
            '{"score": 75, "label": "okay"}',
        ])
        loader = PromptLoader()
        engine = LLMEngine(provider, loader, max_retries=2)

        result = await engine.generate_structured(
            "job_matching",
            ScoreModel,
            company="ACME",
            title="Engineer",
            location="Remote",
            employment_type="full-time",
            description="Build things",
            name="Jane",
            profile_title="Developer",
            skills="Python",
            experience="5 years",
            education="BS",
        )

        assert result.score == 75
        assert provider.call_count == 2

    @pytest.mark.asyncio
    async def test_generate_structured_raises_after_max_retries(self):
        provider = MockProvider(["bad json", "also bad", "still bad"])
        loader = PromptLoader()
        engine = LLMEngine(provider, loader, max_retries=2)

        with pytest.raises(LLMEngineError, match="ScoreModel"):
            await engine.generate_structured(
                "job_matching",
                ScoreModel,
                company="ACME",
                title="Engineer",
                location="Remote",
                employment_type="full-time",
                description="Build things",
                name="Jane",
                profile_title="Developer",
                skills="Python",
                experience="5 years",
                education="BS",
            )

        assert provider.call_count == 3

    @pytest.mark.asyncio
    async def test_generate_structured_handles_markdown_fence(self):
        provider = MockProvider(['```json\n{"score": 95, "label": "excellent"}\n```'])
        loader = PromptLoader()
        engine = LLMEngine(provider, loader)

        result = await engine.generate_structured(
            "job_matching",
            ScoreModel,
            company="ACME",
            title="Engineer",
            location="Remote",
            employment_type="full-time",
            description="Build things",
            name="Jane",
            profile_title="Developer",
            skills="Python",
            experience="5 years",
            education="BS",
        )

        assert result.score == 95

    @pytest.mark.asyncio
    async def test_generate_structured_handles_text_before_json(self):
        provider = MockProvider(['Here is the result:\n{"score": 80, "label": "good"}'])
        loader = PromptLoader()
        engine = LLMEngine(provider, loader)

        result = await engine.generate_structured(
            "job_matching",
            ScoreModel,
            company="ACME",
            title="Engineer",
            location="Remote",
            employment_type="full-time",
            description="Build things",
            name="Jane",
            profile_title="Developer",
            skills="Python",
            experience="5 years",
            education="BS",
        )

        assert result.score == 80

    @pytest.mark.asyncio
    async def test_parse_json_strips_surrounding_text(self):
        raw = "Some text before\n{\"key\": \"value\"}\nSome text after"
        result = LLMEngine._parse_json(raw)
        assert result == {"key": "value"}

    @pytest.mark.asyncio
    async def test_parse_json_with_markdown_fence(self):
        raw = "```json\n{\"key\": \"value\"}\n```"
        result = LLMEngine._parse_json(raw)
        assert result == {"key": "value"}

    @pytest.mark.asyncio
    async def test_parse_json_plain_object(self):
        raw = '{"key": "value"}'
        result = LLMEngine._parse_json(raw)
        assert result == {"key": "value"}

    @pytest.mark.asyncio
    async def test_parse_json_array(self):
        raw = '[{"a": 1}, {"b": 2}]'
        result = LLMEngine._parse_json(raw)
        assert result == [{"a": 1}, {"b": 2}]

    @pytest.mark.asyncio
    async def test_build_retry_prompt_appends_context(self):
        original = "Evaluate the following job"
        raw = '{"bad": json}'
        error = "Invalid JSON"
        result = LLMEngine._build_retry_prompt(original, raw, error)
        assert original in result
        assert raw in result
        assert error in result
        assert "valid JSON only" in result
