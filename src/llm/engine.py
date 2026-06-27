from __future__ import annotations

import json
import logging
import re
from typing import Any

from pydantic import BaseModel, ValidationError

from src.llm.base import LLMProvider
from src.prompts.loader import PromptLoader

logger = logging.getLogger("job-bot.llm.engine")


class LLMEngineError(Exception):
    pass


class LLMEngine:
    def __init__(
        self, provider: LLMProvider, prompt_loader: PromptLoader, max_retries: int = 2
    ) -> None:
        self._provider = provider
        self._prompt_loader = prompt_loader
        self._max_retries = max_retries

    async def generate_text(self, template: str, **variables: Any) -> str:
        prompt = self._prompt_loader.render(template, **variables)
        result = await self._provider.generate(prompt)
        return result.strip()

    async def generate_structured(
        self,
        template: str,
        model: type[BaseModel],
        **variables: Any,
    ) -> BaseModel:
        prompt = self._prompt_loader.render(template, **variables)
        last_error: Exception | None = None

        for attempt in range(self._max_retries + 1):
            try:
                raw = await self._provider.generate(prompt)
                data = self._parse_json(raw)
                validated = model.model_validate(data)
                if attempt > 0:
                    logger.info("Structured generation succeeded on retry %d", attempt + 1)
                return validated
            except (json.JSONDecodeError, ValidationError, ValueError) as e:
                last_error = e
                logger.warning(
                    "Structured generation attempt %d failed: %s",
                    attempt + 1,
                    e,
                )
                if attempt < self._max_retries:
                    prompt = self._build_retry_prompt(prompt, raw, str(e))

        msg = f"Failed to generate valid {model.__name__} after {self._max_retries + 1} attempts"
        raise LLMEngineError(msg) from last_error

    @staticmethod
    def _parse_json(raw: str) -> Any:
        text = raw.strip()
        text = re.sub(r"^```(?:json)?\s*\n?", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\n?```\s*$", "", text)

        start_match = re.search(r"[\{\[]", text)
        if not start_match:
            raise json.JSONDecodeError("No JSON object/array found", text, 0)

        start = start_match.start()
        open_char = text[start]
        close_char = "}" if open_char == "{" else "]"

        depth = 0
        end = start
        for i in range(start, len(text)):
            ch = text[i]
            if ch == open_char:
                depth += 1
            elif ch == close_char:
                depth -= 1
                if depth == 0:
                    end = i + 1
                    break

        if depth != 0:
            raise json.JSONDecodeError("Unmatched brackets in JSON", text, start)

        return json.loads(text[start:end])

    @staticmethod
    def _build_retry_prompt(original: str, raw: str, error: str) -> str:
        return (
            f"{original}\n\n"
            f"Your previous response could not be parsed:\n"
            f"```\n{raw}\n```\n\n"
            f"Parse error: {error}\n\n"
            "Please respond with valid JSON only, no markdown formatting."
        )
