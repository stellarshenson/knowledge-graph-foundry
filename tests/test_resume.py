"""Kill-resume ingestion proof (S5): a run that dies mid-ingest resumes
without re-processing completed documents; a revised file re-ingests."""

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
