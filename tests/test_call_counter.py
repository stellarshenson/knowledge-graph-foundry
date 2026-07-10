"""H363/H362 instrumentation: the engine counts logical LLM calls thread-safely."""

import threading

from pydantic import BaseModel

from knowledge_graph_foundry.engines.local_gpu import LocalGpuEngine
from knowledge_graph_foundry.settings import LLMSettings


class _Out(BaseModel):
    text: str


def _engine() -> LocalGpuEngine:
    return LocalGpuEngine(
        LLMSettings(engine="local-gpu", model="stub", base_url="http://localhost:9")
    )


def test_complete_increments_calls(monkeypatch):
    eng = _engine()

    class _Completions:
        def create(self, **kwargs):
            return _Out(text="ok")

    class _Chat:
        completions = _Completions()

    class _Client:
        chat = _Chat()

    eng._client = _Client()
    assert eng.calls == 0
    eng.complete([{"role": "user", "content": "x"}], _Out)
    eng.complete([{"role": "user", "content": "y"}], _Out)
    assert eng.calls == 2


def test_complete_text_increments_calls(monkeypatch):
    eng = _engine()

    class _Msg:
        content = "ok"

    class _Choice:
        message = _Msg()

    class _Resp:
        choices = [_Choice()]

    import litellm

    monkeypatch.setattr(litellm, "completion", lambda **kwargs: _Resp())
    eng.complete_text("sys", "usr")
    assert eng.calls == 1


def test_counter_thread_safe():
    eng = _engine()
    n, threads = 200, []
    for _ in range(8):
        t = threading.Thread(target=lambda: [eng._count_call() for _ in range(n)])
        threads.append(t)
        t.start()
    for t in threads:
        t.join()
    assert eng.calls == 8 * n
