"""LLM cassette recorder and replayer for deterministic testing.

Provides a mock instructor client that replays pre-recorded LLM responses
from JSON cassette files. Supports both ``client.chat.completions.create()``
and ``client.create()`` call patterns used by instructor.

Recording mode: wrap a real instructor client to capture responses.
Replay mode: load a cassette file and return responses in sequence.

Cassette format (JSON)::

    {
      "description": "what this cassette tests",
      "calls": [
        {
          "method": "chat.completions.create",
          "response_model": "ExtractionResponse",
          "kwargs": {"model": "bedrock/test", "temperature": 0.0},
          "response": { ... serialized pydantic model ... }
        }
      ]
    }
"""

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any

from pydantic import BaseModel

# Registry of response model classes by name, populated lazily.
_MODEL_REGISTRY: dict[str, type[BaseModel]] = {}


class _TypeChoice(BaseModel):
    """Mirror of type_resolver.py inline _TypeChoice model."""

    chosen_type: str
    reasoning: str = ""


class _CrossTypeMergeDecision(BaseModel):
    """Mirror of deferred_dedup.py inline _CrossTypeMergeDecision model."""

    should_merge: bool
    chosen_type: str
    reasoning: str = ""


def _ensure_registry() -> None:
    """Populate the model registry with known response models."""
    if _MODEL_REGISTRY:
        return

    from kgf.curing.generative import CureDecision, CureProbe, RecureDecision
    from kgf.curing.type_clustering import TypeClusteringResult
    from kgf.extraction.response_models import ExtractionResponse
    from kgf.extraction.schema_signals import SchemaSignals

    for cls in (
        ExtractionResponse,
        CureProbe,
        CureDecision,
        RecureDecision,
        TypeClusteringResult,
        SchemaSignals,
        _TypeChoice,
        _CrossTypeMergeDecision,
    ):
        _MODEL_REGISTRY[cls.__name__] = cls


def _resolve_model(name: str) -> type[BaseModel]:
    """Resolve a response model class by name."""
    _ensure_registry()
    if name not in _MODEL_REGISTRY:
        raise KeyError(f"Unknown response model: {name!r}. Known: {sorted(_MODEL_REGISTRY)}")
    return _MODEL_REGISTRY[name]


# ---------------------------------------------------------------------------
# Cassette data structures
# ---------------------------------------------------------------------------


class CassetteCall:
    """Single recorded LLM call."""

    def __init__(
        self,
        method: str,
        response_model_name: str,
        response_data: dict[str, Any],
        kwargs: dict[str, Any] | None = None,
    ):
        self.method = method
        self.response_model_name = response_model_name
        self.response_data = response_data
        self.kwargs = kwargs or {}

    def to_dict(self) -> dict[str, Any]:
        return {
            "method": self.method,
            "response_model": self.response_model_name,
            "kwargs": self.kwargs,
            "response": self.response_data,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CassetteCall:
        return cls(
            method=data["method"],
            response_model_name=data["response_model"],
            response_data=data["response"],
            kwargs=data.get("kwargs", {}),
        )

    def replay(self) -> BaseModel:
        """Deserialize the response into the appropriate Pydantic model."""
        model_cls = _resolve_model(self.response_model_name)
        return model_cls.model_validate(self.response_data)


class Cassette:
    """Collection of recorded LLM calls."""

    def __init__(self, description: str = "", calls: list[CassetteCall] | None = None):
        self.description = description
        self.calls = calls or []

    def to_dict(self) -> dict[str, Any]:
        return {
            "description": self.description,
            "calls": [c.to_dict() for c in self.calls],
        }

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2) + "\n")

    @classmethod
    def load(cls, path: Path) -> Cassette:
        data = json.loads(path.read_text())
        return cls(
            description=data.get("description", ""),
            calls=[CassetteCall.from_dict(c) for c in data["calls"]],
        )


# ---------------------------------------------------------------------------
# Replay client
# ---------------------------------------------------------------------------


class ReplayClient:
    """Mock instructor client that replays cassette responses in order.

    Supports both call patterns:
    - ``client.chat.completions.create(...)``
    - ``client.create(...)``

    Tracks call history for assertions.
    """

    def __init__(self, cassette: Cassette):
        self._cassette = cassette
        self._index = 0
        self._lock = threading.Lock()
        self.call_log: list[dict[str, Any]] = []

        # Wire up both call patterns
        self.chat = _ChatNamespace(self)
        self.create = self._create

    def _next_response(self, method: str, **kwargs: Any) -> BaseModel:
        """Return the next pre-recorded response (thread-safe)."""
        with self._lock:
            if self._index >= len(self._cassette.calls):
                raise IndexError(
                    f"Cassette exhausted after {self._index} calls "
                    f"(cassette: {self._cassette.description!r})"
                )

            call = self._cassette.calls[self._index]
            self._index += 1

            if call.method != method:
                raise ValueError(
                    f"Call {self._index}: expected method {call.method!r}, "
                    f"got {method!r}"
                )

            self.call_log.append({
                "method": method,
                "response_model": call.response_model_name,
                "kwargs": kwargs,
            })

        return call.replay()

    def _create(self, **kwargs: Any) -> BaseModel:
        return self._next_response("create", **kwargs)

    @property
    def calls_made(self) -> int:
        return self._index

    @property
    def calls_remaining(self) -> int:
        return len(self._cassette.calls) - self._index

    @classmethod
    def from_cassette_file(cls, path: str | Path) -> ReplayClient:
        return cls(Cassette.load(Path(path)))


class _ChatNamespace:
    """Mimics ``client.chat.completions.create()`` chain."""

    def __init__(self, client: ReplayClient):
        self.completions = _CompletionsNamespace(client)


class _CompletionsNamespace:
    def __init__(self, client: ReplayClient):
        self._client = client

    def create(self, **kwargs: Any) -> BaseModel:
        return self._client._next_response("chat.completions.create", **kwargs)


# ---------------------------------------------------------------------------
# Recording client (wraps a real instructor client)
# ---------------------------------------------------------------------------


class RecordingClient:
    """Wraps a real instructor client and records all calls to a cassette.

    Usage::

        real_client = instructor.from_litellm(litellm.completion)
        recorder = RecordingClient(real_client, "extraction session")
        # use recorder in place of client
        entities, rels = extract_chunk(chunk, prompt, model, recorder, ...)
        recorder.save("tests/fixtures/llm_cassettes/my_session.json")
    """

    def __init__(self, real_client: Any, description: str = ""):
        self._real = real_client
        self._cassette = Cassette(description=description)
        self.chat = _RecordingChatNamespace(self)

    def create(self, **kwargs: Any) -> BaseModel:
        result = self._real.create(**kwargs)
        self._record("create", kwargs, result)
        return result

    def _record(self, method: str, kwargs: dict[str, Any], result: BaseModel) -> None:
        model_name = type(result).__name__
        # Store only serializable kwargs subset
        safe_kwargs = {}
        if "model" in kwargs:
            safe_kwargs["model"] = kwargs["model"]
        if "temperature" in kwargs:
            safe_kwargs["temperature"] = kwargs["temperature"]

        self._cassette.calls.append(
            CassetteCall(
                method=method,
                response_model_name=model_name,
                response_data=result.model_dump(),
                kwargs=safe_kwargs,
            )
        )

    def save(self, path: str | Path) -> None:
        self._cassette.save(Path(path))

    @property
    def cassette(self) -> Cassette:
        return self._cassette


class _RecordingChatNamespace:
    def __init__(self, client: RecordingClient):
        self.completions = _RecordingCompletionsNamespace(client)


class _RecordingCompletionsNamespace:
    def __init__(self, client: RecordingClient):
        self._client = client

    def create(self, **kwargs: Any) -> BaseModel:
        result = self._client._real.chat.completions.create(**kwargs)
        self._client._record("chat.completions.create", kwargs, result)
        return result
