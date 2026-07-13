"""R26-H274 external answer cache: unit coverage + the query() wrapper."""

from types import SimpleNamespace

from knowledge_graph_foundry.graph.answer_cache import AnswerCache, cache_key
from knowledge_graph_foundry.pipeline import Foundry


def test_cache_roundtrip(tmp_path):
    c = AnswerCache(tmp_path / "c.json")
    assert c.lookup("Q", "fp1") is None
    c.store("Q", "fp1", {"answer": "A"})
    # a fresh instance reloads from disk
    assert AnswerCache(tmp_path / "c.json").lookup("Q", "fp1") == {"answer": "A"}


def test_cache_fingerprint_invalidation(tmp_path):
    c = AnswerCache(tmp_path / "c.json")
    c.store("Q", "fp1", {"answer": "A"})
    # a different graph generation never matches
    assert c.lookup("Q", "fp2") is None
    # storing under the new fingerprint prunes the superseded entry
    c.store("Q", "fp2", {"answer": "B"})
    c2 = AnswerCache(tmp_path / "c.json")
    assert c2.lookup("Q", "fp1") is None
    assert c2.lookup("Q", "fp2") == {"answer": "B"}
    assert len(c2._data) == 1  # bounded to the current generation


def test_cache_key_normalization():
    assert cache_key("What Is X?", "fp") == cache_key("what is  x?", "fp")
    assert cache_key("Q", "fp1") != cache_key("Q", "fp2")


def _fake_foundry(tmp_path, enabled, calls, docs=("d1",)):
    return SimpleNamespace(
        settings=SimpleNamespace(
            answer_cache=SimpleNamespace(enabled=enabled, path=str(tmp_path / "c.json"))
        ),
        _load_state=lambda: {"processed_documents": list(docs)},
        _query_uncached=lambda q: (
            calls.append(q),
            {"answer": "A", "supporting_entities": [], "path": "vector"},
        )[1],
    )


def test_query_cache_disabled_is_passthrough(tmp_path):
    calls: list = []
    fake = _fake_foundry(tmp_path, enabled=False, calls=calls)
    r = Foundry.query(fake, "Q?")
    assert r["path"] == "vector" and len(calls) == 1
    assert not (tmp_path / "c.json").exists()  # no cache file when disabled


def test_query_cache_hit_skips_llm(tmp_path):
    calls: list = []
    fake = _fake_foundry(tmp_path, enabled=True, calls=calls)
    r1 = Foundry.query(fake, "What is X?")
    assert r1["path"] == "vector" and len(calls) == 1
    # normalized-identical question, same graph generation -> served from cache
    r2 = Foundry.query(fake, "what is  x?")
    assert r2["answer"] == "A" and r2["path"] == "cache"
    assert len(calls) == 1  # _query_uncached not called again


def test_query_cache_invalidates_on_graph_change(tmp_path):
    calls: list = []
    fake = _fake_foundry(tmp_path, enabled=True, calls=calls, docs=("d1",))
    Foundry.query(fake, "Q?")
    assert len(calls) == 1
    # graph mutates -> fingerprint changes -> the cached answer no longer matches
    fake._load_state = lambda: {"processed_documents": ["d1", "d2"]}
    r = Foundry.query(fake, "Q?")
    assert r["path"] == "vector" and len(calls) == 2
