"""Frontier engine: litellm + instructor to Bedrock / Anthropic / OpenAI."""

from __future__ import annotations

import os
from typing import TypeVar

from pydantic import BaseModel

from knowledge_graph_foundry.engines.base import EngineError
from knowledge_graph_foundry.settings import LLMSettings

T = TypeVar("T", bound=BaseModel)


class FrontierEngine:
    name = "frontier"

    def __init__(self, cfg: LLMSettings):
        import instructor
        import litellm

        self.cfg = cfg
        if cfg.region and cfg.model.startswith("bedrock/"):
            os.environ.setdefault("AWS_REGION_NAME", cfg.region)
        litellm.suppress_debug_info = True
        # reasoning models (e.g. Opus 4.8) reject temperature=0; drop rather than fail
        litellm.drop_params = True
        self._client = instructor.from_litellm(litellm.completion)

    def complete(self, messages: list[dict[str, str]], response_model: type[T]) -> T:
        try:
            return self._client.chat.completions.create(
                model=self.cfg.model,
                messages=messages,
                response_model=response_model,
                temperature=self.cfg.temperature,
                timeout=self.cfg.timeout,
                max_retries=self.cfg.max_retries,
            )
        except Exception as exc:
            raise EngineError(f"frontier engine failed: {exc}") from exc
