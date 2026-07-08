"""Kill-resume ingestion proof (S5): a run that dies mid-ingest resumes
without re-processing completed documents; a revised file re-ingests."""

import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from knowledge_graph_foundry.models import Entity, Ontology
from knowledge_graph_foundry.pipeline import Foundry
from knowledge_graph_foundry.settings import CuringSettings, Settings


def _files(tmp_path, names):
    paths = []
    for n in names:
        p = tmp_path / n
        p.write_text(f"content of {n}")
        paths.append(p)
    return paths


def _foundry(store: dict) -> Foundry:
    settings = Settings(
        curing=CuringSettings(min_documents=50, max_fluid_documents=100)  # never cure
    )
    f = Foundry(settings)
    f._driver = MagicMock()
    f._load_state = lambda: dict(store)
    f._save_state = lambda state: store.update(state)
    return f


def _seed_state(store: dict) -> None:
    store.update(
        {
            "fsm_state": "INITIALIZING",
            "purpose": "test purpose",
            "ontology": Ontology(purpose="test purpose").model_dump(),
        }
    )


def _entity_for(path) -> list[Entity]:
    return [Entity.create(f"entity-{path.name}", types=["Thing"], description="x")]


@pytest.fixture
def lease_patches():
    with (
        patch("knowledge_graph_foundry.graph.lock.acquire_lease", return_value=True),
        patch("knowledge_graph_foundry.graph.lock.heartbeat", return_value=True),
        patch("knowledge_graph_foundry.graph.lock.release_lease"),
    ):
        yield


class TestKillResume:
    def test_killed_run_resumes_without_reprocessing(self, tmp_path, lease_patches):
        _files(tmp_path, ["a.txt", "b.txt", "c.txt"])
        store: dict = {}
        _seed_state(store)

        # run 1: dies (uncaught BaseException) while extracting the second file
        f1 = _foundry(store)
        calls_run1 = []

        def dying_extract(path, purpose, ontology):
            calls_run1.append(path.name)
            if len(calls_run1) == 2:
                raise KeyboardInterrupt  # process killed mid-run
            return _entity_for(path), []

        f1._extract_file = dying_extract
        f1._embed = lambda e: e
        with pytest.raises(KeyboardInterrupt):
            f1.ingest(tmp_path)
        assert store["documents_processed"] == 1  # first document persisted

        # run 2: resumes - completed document is skipped, the rest processed
        f2 = _foundry(store)
        calls_run2 = []

        def working_extract(path, purpose, ontology):
            calls_run2.append(path.name)
            return _entity_for(path), []

        f2._extract_file = working_extract
        f2._embed = lambda e: e
        summary = f2.ingest(tmp_path)

        assert calls_run2 == ["b.txt", "c.txt"]  # a.txt never re-extracted
        assert summary["documents"] == 2
        assert store["documents_processed"] == 3
        assert len(store["processed_documents"]) == 3

    def test_revised_file_reingests(self, tmp_path, lease_patches):
        (paths,) = (_files(tmp_path, ["a.txt"]),)
        store: dict = {}
        _seed_state(store)

        f1 = _foundry(store)
        f1._extract_file = lambda p, pu, o: (_entity_for(p), [])
        f1._embed = lambda e: e
        f1.ingest(tmp_path)
        assert store["documents_processed"] == 1

        # unchanged file: skipped on the next run
        f2 = _foundry(store)
        f2._extract_file = MagicMock(side_effect=lambda p, pu, o: (_entity_for(p), []))
        f2._embed = lambda e: e
        assert f2.ingest(tmp_path)["documents"] == 0
        f2._extract_file.assert_not_called()

        # revised content, same name: fingerprint changes, re-ingested
        paths[0].write_text("REVISED content of a.txt")
        f3 = _foundry(store)
        f3._extract_file = MagicMock(side_effect=lambda p, pu, o: (_entity_for(p), []))
        f3._embed = lambda e: e
        assert f3.ingest(tmp_path)["documents"] == 1
        f3._extract_file.assert_called_once()


class TestRepair:
    """R04 first slice: targeted repair re-extracts named sources with focus."""

    def test_repair_requires_stable(self, tmp_path, lease_patches):
        store: dict = {}
        _seed_state(store)  # INITIALIZING
        f = _foundry(store)
        with pytest.raises(Exception, match="STABLE"):
            f.repair("some question", [tmp_path / "a.txt"])

    def test_repair_bypasses_fingerprint_and_focuses_extraction(self, tmp_path, lease_patches):
        paths = _files(tmp_path, ["a.txt"])
        store: dict = {}
        _seed_state(store)
        store["fsm_state"] = "STABLE"
        # simulate a completed ingest of a.txt (fingerprint recorded)
        import hashlib

        fp = f"a.txt:{hashlib.sha1(paths[0].read_bytes()).hexdigest()[:16]}"
        store["processed_documents"] = [fp]

        f = _foundry(store)
        seen = {}

        def spy_extract(path, purpose, ontology):
            seen["path"] = path.name
            seen["purpose"] = purpose
            return _entity_for(path), []

        f._extract_file = spy_extract
        f._embed = lambda e: e
        f._stable_load = lambda e, r, o, c: (0.0, 0)
        f.settings.graphrag.propositions_enabled = False
        summary = f.repair("what is the weight of device X?", [paths[0]])

        assert seen["path"] == "a.txt"  # re-extracted despite the fingerprint
        assert "what is the weight of device X?" in seen["purpose"]  # focus injected
        assert summary["documents"] == 1


class TestRepurpose:
    """Long-lived graphs survive their owners changing the use case."""

    def test_repurpose_requires_stable(self, lease_patches):
        store: dict = {}
        _seed_state(store)  # INITIALIZING
        f = _foundry(store)
        with pytest.raises(Exception, match="STABLE"):
            f.repurpose("a different objective")

    def test_repurpose_keeps_history_and_steers_future_extraction(
        self, tmp_path, lease_patches
    ):
        _files(tmp_path, ["a.txt"])
        store: dict = {}
        _seed_state(store)
        store["fsm_state"] = "STABLE"

        f = _foundry(store)
        result = f.repurpose("new objective for the same graph")
        assert result["previous_purpose"] == "test purpose"
        assert result["purpose_changes"] == 1
        assert store["purpose"] == "new objective for the same graph"
        assert store["purpose_history"][0]["purpose"] == "test purpose"
        assert store["purpose_history"][0]["replaced_at"]

        # identical purpose is rejected
        with pytest.raises(Exception, match="identical"):
            f.repurpose("new objective for the same graph")

        # a subsequent ingest extracts under the NEW purpose
        f2 = _foundry(store)
        f2._load_state = lambda: dict(store)
        seen = {}

        def spy_extract(path, purpose, ontology):
            seen["purpose"] = purpose
            return _entity_for(path), []

        f2._extract_file = spy_extract
        f2._embed = lambda e: e
        f2.ingest(tmp_path)
        assert seen["purpose"] == "new objective for the same graph"


class TestTextHeavyRouting:
    """DEF-2: a structured file with text-heavy columns ingests one row = one
    document (own resume fingerprint, own curing contribution); short-column
    structured files keep the whole-file mapping path."""

    @staticmethod
    def _jsonl(tmp_path, rows):
        path = tmp_path / "articles.jsonl"
        path.write_text("\n".join(json.dumps(r) for r in rows))
        return path

    def test_text_heavy_rows_become_own_documents(self, tmp_path, lease_patches):
        rows = [{"title": f"t{i}", "body": f"article {i} " + "x" * 500} for i in range(3)]
        path = self._jsonl(tmp_path, rows)
        store: dict = {}
        _seed_state(store)

        f = _foundry(store)
        seen = []

        def spy_text_extract(document, source_name, purpose, ontology):
            seen.append(document)
            name = f"e-{document.metadata['row_index']}"
            return [Entity.create(name, types=["Thing"], description="x")], []

        f._extract_text_document = spy_text_extract
        f._extract_file = MagicMock()  # the mapping path must not fire
        f._embed = lambda e: e
        summary = f.ingest(path)

        assert summary["documents"] == 3
        f._extract_file.assert_not_called()
        assert [d.metadata["row_index"] for d in seen] == [0, 1, 2]
        assert len({d.id for d in seen}) == 3  # each row is its own document
        assert all(f"article {i} " in seen[i].text for i in range(3))
        fingerprints = store["processed_documents"]
        assert len(fingerprints) == 3
        assert all("#row" in fp for fp in fingerprints)  # per-row resume fingerprints

    def test_short_column_structured_keeps_mapping_path(self, tmp_path, lease_patches):
        rows = [{"name": f"n{i}", "price": i} for i in range(3)]
        path = self._jsonl(tmp_path, rows)
        store: dict = {}
        _seed_state(store)

        f = _foundry(store)
        f._extract_file = MagicMock(side_effect=lambda p, pu, o: (_entity_for(p), []))
        f._extract_text_document = MagicMock()
        f._embed = lambda e: e
        summary = f.ingest(path)

        assert summary["documents"] == 1  # whole file stays one document
        f._extract_file.assert_called_once()
        f._extract_text_document.assert_not_called()
        (fp,) = store["processed_documents"]
        assert fp.startswith("articles.jsonl:")
        assert "#row" not in fp  # file-level fingerprint unchanged

    def test_text_heavy_rows_resume_individually(self, tmp_path, lease_patches):
        rows = [{"body": f"article {i} " + "x" * 500} for i in range(3)]
        path = self._jsonl(tmp_path, rows)
        store: dict = {}
        _seed_state(store)

        def extract(document, source_name, purpose, ontology):
            name = f"e-{document.metadata['row_index']}"
            return [Entity.create(name, types=["Thing"], description="x")], []

        f1 = _foundry(store)
        f1._extract_text_document = extract
        f1._embed = lambda e: e
        assert f1.ingest(path)["documents"] == 3

        # unchanged rows: all skipped on the next run
        f2 = _foundry(store)
        f2._extract_text_document = MagicMock()
        f2._embed = lambda e: e
        assert f2.ingest(path)["documents"] == 0
        f2._extract_text_document.assert_not_called()

        # revise ONE row: only that row's fingerprint changes and re-ingests
        rows[1]["body"] = "REVISED " + rows[1]["body"]
        path.write_text("\n".join(json.dumps(r) for r in rows))
        f3 = _foundry(store)
        seen = []

        def spy(document, source_name, purpose, ontology):
            seen.append(document.metadata["row_index"])
            return extract(document, source_name, purpose, ontology)

        f3._extract_text_document = spy
        f3._embed = lambda e: e
        assert f3.ingest(path)["documents"] == 1
        assert seen == [1]

    def test_empty_text_rows_skipped(self, tmp_path, lease_patches):
        rows = [
            {"body": "article one " + "x" * 500},
            {"body": ""},
            {"body": None},
        ]
        path = self._jsonl(tmp_path, rows)
        store: dict = {}
        _seed_state(store)

        f = _foundry(store)
        f._engine = MagicMock()
        f.settings.load.provenance_nodes = False

        def fake_extract_document(chunks, purpose, ontology, engine, **kwargs):
            return SimpleNamespace(
                entities=[Entity.create("e", types=["Thing"], description="x")],
                relationships=[],
            )

        f._embed = lambda e: e
        with patch(
            "knowledge_graph_foundry.extraction.extract_document", fake_extract_document
        ):
            summary = f.ingest(path)

        # empty/None rows chunk to nothing and are skipped as documents
        assert summary["documents"] == 1
        assert len(store["processed_documents"]) == 1
