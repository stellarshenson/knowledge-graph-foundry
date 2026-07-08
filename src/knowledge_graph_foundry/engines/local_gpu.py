"""Local GPU engine: OpenAI-compatible endpoint (e.g. vLLM) via litellm."""

from __future__ import annotations

from typing import TypeVar

from pydantic import BaseModel

from knowledge_graph_foundry.engines.base import EngineError
from knowledge_graph_foundry.settings import LLMSettings

T = TypeVar("T", bound=BaseModel)


class LocalGpuEngine:
    name = "local-gpu"

    def __init__(self, cfg: LLMSettings):
        import instructor

        # DEF-6: instructor 1.15.4 registers the (OPENAI, Mode.JSON) handler only
        # as an import side effect of this module. Without the explicit import,
        # from_litellm below raises RegistryError depending on interpreter import
        # order (notebooks carried the workaround). Importing it here makes client
        # construction order-independent.
        import instructor.v2.providers.openai.handlers  # noqa: F401
        import litellm

        if not cfg.base_url:
            raise EngineError(
                "local-gpu engine requires llm.base_url (OpenAI-compatible endpoint)"
            )
        self.cfg = cfg
        litellm.suppress_debug_info = True
        self._client = instructor.from_litellm(litellm.completion, mode=instructor.Mode.JSON)

    def complete(self, messages: list[dict[str, str]], response_model: type[T]) -> T:
        model = self.cfg.model
        if not model.startswith("openai/"):
            model = f"openai/{model}"
        try:
            return self._client.chat.completions.create(
                model=model,
                messages=messages,
                response_model=response_model,
                temperature=self.cfg.temperature,
                timeout=self.cfg.timeout,
                max_retries=self.cfg.max_retries,
                api_base=self.cfg.base_url,
                api_key="local",
            )
        except Exception as exc:
            raise EngineError(f"local-gpu engine failed: {exc}") from exc

    def complete_text(self, system: str, user: str) -> str:
        """Raw text completion via litellm (bypasses instructor) for names-only enumeration."""
        import litellm

        model = self.cfg.model
        if not model.startswith("openai/"):
            model = f"openai/{model}"
        try:
            resp = litellm.completion(
                model=model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                temperature=self.cfg.temperature,
                timeout=self.cfg.timeout,
                api_base=self.cfg.base_url,
                api_key="local",
            )
            return resp.choices[0].message.content or ""
        except Exception as exc:
            raise EngineError(f"local-gpu engine failed: {exc}") from exc
