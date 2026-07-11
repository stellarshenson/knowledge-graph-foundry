"""R30-H362 throughput calibration: cache keying, warm-start band, cold ramp."""

import json

from knowledge_graph_foundry.extraction.throughput import (
    ThroughputCache,
    cold_ramp,
    in_band,
    setup_key,
)


class TestSetupKey:
    def test_distinct_setups_distinct_keys(self):
        base = dict(engine="local-gpu", endpoint="http://x:8010/v1", model="m")
        k1 = setup_key(**base, extraction_config={"recipe": "enumerate"})
        assert setup_key(**base, extraction_config={"recipe": "enumerate"}) == k1
        assert setup_key(**base, extraction_config={"recipe": "mention"}) != k1
        assert setup_key(**{**base, "model": "m2"}, extraction_config={"recipe": "enumerate"}) != k1


class TestCache:
    def _entry(self, **over):
        return {
            "knee_concurrency": 56,
            "tok_s_generation": 594.5,
            "chunks_per_min": 2.4,
            "provenance": "measured",
            **over,
        }

    def test_put_get_roundtrip_and_isolation(self, tmp_path):
        cache = ThroughputCache(tmp_path / "cache.json")
        cache.put("k1", self._entry())
        cache.put("k2", self._entry(knee_concurrency=8))
        assert cache.get("k1")["knee_concurrency"] == 56
        assert cache.get("k2")["knee_concurrency"] == 8  # k1 untouched by k2
        assert cache.get("missing") is None

    def test_unreadable_cache_is_cold_path(self, tmp_path):
        p = tmp_path / "cache.json"
        p.write_text("{corrupt")
        assert ThroughputCache(p).get("k") is None

    def test_ewma_smoothing_and_shipped_flip(self, tmp_path):
        cache = ThroughputCache(tmp_path / "cache.json")
        cache.put("k", self._entry(provenance="shipped"))
        out = cache.smooth("k", {"tok_s_generation": 500.0, "chunks_per_min": 2.0})
        assert out["provenance"] == "measured"  # shipped entries replaced outright
        assert out["tok_s_generation"] == 500.0
        out2 = cache.smooth("k", {"tok_s_generation": 600.0, "chunks_per_min": 3.0})
        assert 500.0 < out2["tok_s_generation"] < 600.0  # EWMA, not replace


class TestWarmStartBand:
    def test_in_and_out_of_band(self):
        entry = {"chunks_per_min": 2.4, "chunks_per_min_std": 0.2}
        assert in_band(entry, 2.5)
        assert not in_band(entry, 4.0)  # > 3 sigma -> recalibrate

    def test_default_spread_when_no_variance_recorded(self):
        assert in_band({"chunks_per_min": 2.4}, 2.4)
        assert not in_band({}, 2.4)  # no expectation -> cannot verify


class TestColdRamp:
    def test_early_exit_and_knee_share(self):
        # gen tok/s doubles to c=4 then flattens: doubling gain < 20% at c=8
        curve = {1: 100.0, 2: 200.0, 4: 380.0, 8: 400.0}
        probed = []

        def probe(c):
            probed.append(c)
            return {"tok_s_generation": curve[c], "chunks_per_min": c / 2, "tainted": False}

        out = cold_ramp(probe)
        assert probed == [1, 2, 4, 8]  # early exit fired, no c=16 probe
        assert out["knee_concurrency"] == 4  # smallest c within 90% of peak 400

    def test_capacity_cliff_stops_ramp(self):
        def probe(c):
            if c >= 4:
                return {"tok_s_generation": 50.0, "chunks_per_min": 0.5, "tainted": True}
            return {"tok_s_generation": 100.0 * c, "chunks_per_min": c, "tainted": False}

        out = cold_ramp(probe)
        assert out["knee_concurrency"] == 2  # chosen below the cliff


class TestWarmStartWiring:
    """R30-H362: extraction concurrency resolves from the cache under auto_calibrate."""

    def _foundry(self, tmp_path, monkeypatch, auto, entry=None):
        from knowledge_graph_foundry.extraction import throughput
        from knowledge_graph_foundry.pipeline import Foundry
        from knowledge_graph_foundry.settings import Settings

        monkeypatch.setattr(throughput, "DEFAULT_CACHE_PATH", tmp_path / "cache.json")
        s = Settings()
        s.extraction.auto_calibrate = auto
        s.extraction.concurrency = 4
        if entry:
            cache = throughput.ThroughputCache(tmp_path / "cache.json")
            key = throughput.setup_key(
                s.llm.engine, s.llm.base_url or getattr(s.llm, "region", "") or "",
                s.llm.model, {"recipe": s.extraction.recipe, "timeout": s.llm.timeout},
            )
            cache.put(key, entry)
        return Foundry(s)

    def test_off_uses_configured(self, tmp_path, monkeypatch):
        f = self._foundry(tmp_path, monkeypatch, auto=False)
        assert f._extraction_concurrency() == 4

    def test_warm_start_from_cache(self, tmp_path, monkeypatch):
        f = self._foundry(tmp_path, monkeypatch, auto=True,
                          entry={"knee_concurrency": 56, "provenance": "measured"})
        assert f._extraction_concurrency() == 56

    def test_cache_miss_falls_back(self, tmp_path, monkeypatch):
        f = self._foundry(tmp_path, monkeypatch, auto=True)
        assert f._extraction_concurrency() == 4
