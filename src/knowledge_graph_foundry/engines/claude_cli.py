"""Claude CLI engine: subprocess `claude -p` with JSON-schema prompting.

The CLI returns free text, so the schema is appended as an instruction and
the reply parsed as JSON. One repair re-prompt on parse/validation failure,
then EngineError carrying the raw output.
"""

from __future__ import annotations

import json
import re
import subprocess
from typing import TypeVar

from pydantic import BaseModel, ValidationError

from knowledge_graph_foundry.engines.base import EngineError
from knowledge_graph_foundry.settings import LLMSettings

T = TypeVar("T", bound=BaseModel)

_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


def _extract_json(text: str) -> str:
    """Strip code fences and take the outermost JSON object."""
    cleaned = _FENCE.sub("", text.strip()).strip()
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("no JSON object in output")
    return cleaned[start : end + 1]


class ClaudeCliEngine:
    name = "claude-cli"

    def __init__(self, cfg: LLMSettings):
        self.cfg = cfg

    def _run(self, prompt: str) -> str:
        result = subprocess.run(
            [self.cfg.claude_cli_path, "-p", prompt],
            capture_output=True,
            text=True,
            timeout=self.cfg.timeout * 4,
        )
        if result.returncode != 0:
            raise EngineError(
                f"claude CLI exited {result.returncode}: {result.stderr[:500]}",
                raw_output=result.stdout,
            )
        return result.stdout

    def complete(self, messages: list[dict[str, str]], response_model: type[T]) -> T:
        schema = json.dumps(response_model.model_json_schema(), indent=None)
        prompt = "\n\n".join(m["content"] for m in messages)
        prompt += (
            "\n\nRespond with ONLY a JSON object valid against this JSON schema, "
            f"no prose, no code fences:\n{schema}"
        )
        raw = self._run(prompt)
        for attempt in range(2):
            try:
                return response_model.model_validate_json(_extract_json(raw))
            except (ValueError, ValidationError) as exc:
                if attempt == 1:
                    raise EngineError(
                        f"claude CLI output failed validation: {exc}", raw_output=raw
                    ) from exc
                raw = self._run(
                    prompt + f"\n\nYour previous reply failed validation with: {exc}\n"
                    "Reply again with ONLY the corrected JSON object."
                )
        raise EngineError("unreachable")
