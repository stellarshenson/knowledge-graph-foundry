"""Engine protocol - the single LLM interface used by the whole pipeline."""

from __future__ import annotations

from typing import Protocol, TypeVar, runtime_checkable

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class EngineError(RuntimeError):
    """Engine failure carrying the raw model output when available."""

    def __init__(self, message: str, raw_output: str = ""):
        super().__init__(message)
        self.raw_output = raw_output


@runtime_checkable
class Engine(Protocol):
    """Complete a chat and return a validated instance of response_model."""

    name: str

    def complete(self, messages: list[dict[str, str]], response_model: type[T]) -> T: ...
