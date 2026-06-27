import json
import logging

import httpx

from src.llm.base import LLMProvider

logger = logging.getLogger("job-bot.llm.ollama")


class OllamaError(Exception):
    pass


class OllamaProvider(LLMProvider):
    def __init__(
        self, model: str = "gemma3", base_url: str = "http://localhost:11434", timeout: int = 60
    ) -> None:
        self._model = model
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

    async def generate(self, prompt: str) -> str:
        url = f"{self._base_url}/api/generate"
        payload = {"model": self._model, "prompt": prompt, "stream": False}

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                data = response.json()
        except httpx.RequestError as e:
            msg = f"Failed to reach Ollama at {self._base_url}: {e}"
            raise OllamaError(msg) from e
        except json.JSONDecodeError as e:
            msg = f"Ollama returned non-JSON response: {e}"
            raise OllamaError(msg) from e
        except httpx.HTTPStatusError as e:
            msg = f"Ollama returned error {e.response.status_code}: {e.response.text}"
            raise OllamaError(msg) from e

        result = data.get("response", "")
        if not isinstance(result, str) or not result.strip():
            raise OllamaError("Ollama returned empty response")

        logger.debug("Ollama generated %d characters", len(result))
        return result
