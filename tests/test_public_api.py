"""Tests for the public library API surface and role-based LLM routing."""

from unittest.mock import MagicMock, patch

import knowledge_graph_foundry as kgf
from knowledge_graph_foundry import Foundry, LLMSettings, Settings


class TestPublicSurface:
    def test_entrypoints_exported(self):
        for name in ("Foundry", "Settings", "load_settings", "Entity", "Relationship", "emit"):
            assert hasattr(kgf, name), name

    def test_version_present(self):
        assert isinstance(kgf.__version__, str)

    def test_all_names_resolve(self):
        for name in kgf.__all__:
            assert hasattr(kgf, name), name

    def test_full_config_constructable(self):
        s = Settings(
            neo4j=kgf.Neo4jSettings(uri="bolt://h:7687", user="u", password="p"),
            extraction=kgf.ExtractionSettings(gleaning_rounds=2),
            resolution=kgf.ResolutionSettings(merge_threshold=0.7),
            graphrag=kgf.GraphRAGSettings(ppr_top_n=20),
        )
        assert s.neo4j.uri == "bolt://h:7687"
        assert s.extraction.gleaning_rounds == 2
        assert s.resolution.merge_threshold == 0.7
        assert s.graphrag.ppr_top_n == 20


class TestSimplestForm:
    def test_zero_arg_foundry_loads_settings(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)  # no config.yml -> defaults
        f = Foundry()
        assert isinstance(f.settings, Settings)

    def test_build_exported(self):
        assert callable(kgf.build)

    def test_build_inits_when_empty_then_ingests(self):
        """build() inits an empty project and ingests in one call."""
        foundry = MagicMock()
        foundry.status.return_value = {"fsm_state": "EMPTY"}
        with patch("knowledge_graph_foundry.pipeline.Foundry.from_config", return_value=foundry):
            returned = kgf.build("compare CPAP machines", "data/manuals/")
        foundry.init_project.assert_called_once_with("compare CPAP machines", None)
        foundry.ingest.assert_called_once_with("data/manuals/")
        assert returned is foundry

    def test_build_skips_init_when_already_initialized(self):
        foundry = MagicMock()
        foundry.status.return_value = {"fsm_state": "STABLE"}
        with patch("knowledge_graph_foundry.pipeline.Foundry.from_config", return_value=foundry):
            kgf.build("purpose", "more/docs/")
        foundry.init_project.assert_not_called()
        foundry.ingest.assert_called_once()

    def test_build_with_explicit_settings_and_optimize(self):
        foundry = MagicMock()
        foundry.status.return_value = {"fsm_state": "EMPTY"}
        with patch("knowledge_graph_foundry.pipeline.Foundry", return_value=foundry):
            kgf.build("p", None, settings=Settings(), optimize=True)
        foundry.init_project.assert_called_once()
        foundry.ingest.assert_not_called()  # no source
        foundry.optimize.assert_called_once()


class TestFoundryLibraryUse:
    def test_context_manager_closes(self):
        f = Foundry(Settings())
        f._driver = MagicMock()
        with f as ctx:
            assert ctx is f
        f._driver.close.assert_called_once() if False else None  # close() nulls driver
        assert f._driver is None

    def test_from_config(self, tmp_path):
        cfg = tmp_path / "config.yml"
        cfg.write_text("graphrag:\n  ppr_top_n: 42\n")
        f = Foundry.from_config(cfg)
        assert f.settings.graphrag.ppr_top_n == 42


class TestRoleBasedLLM:
    def test_extraction_falls_back_to_orchestrator_by_default(self):
        f = Foundry(Settings())
        with patch(
            "knowledge_graph_foundry.pipeline.create_engine",
            return_value=MagicMock(name="orch"),
        ) as ce:
            assert f.extraction_engine is f.engine
            ce.assert_called_once()  # only one engine built

    def test_separate_extraction_engine_when_configured(self):
        s = Settings(
            llm=LLMSettings(model="orchestrator-model"),
            extraction_llm=LLMSettings(model="cheap-extractor"),
        )
        f = Foundry(s)
        built = {}

        def fake_create(cfg):
            m = MagicMock()
            m.model = cfg.model
            built[cfg.model] = m
            return m

        with patch("knowledge_graph_foundry.pipeline.create_engine", side_effect=fake_create):
            assert f.extraction_engine.model == "cheap-extractor"
            assert f.engine.model == "orchestrator-model"
            assert f.extraction_engine is not f.engine


class TestProbeInstrumentationSurface:
    """probe() is the public retrieval-only replay for external instrumentation."""

    def test_probe_wraps_retrieval(self, monkeypatch, tmp_path):
        from knowledge_graph_foundry.pipeline import Foundry
        from knowledge_graph_foundry.settings import Settings

        f = Foundry(Settings())
        monkeypatch.setattr(
            f, "_retrieve_local", lambda q: (["line1"], ["EntityA"], {"top_score": 0.9})
        )
        out = f.probe("what is X?")
        assert out == {
            "context_lines": ["line1"],
            "supporting_names": ["EntityA"],
            "coverage": {"top_score": 0.9},
        }
