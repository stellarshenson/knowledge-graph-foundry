"""DEF-12/R30-H343: cross-document extraction look-ahead.

The `extraction.document_concurrency` knob prefetch-extracts documents in
STABLE/RECURING (frozen ontology) while everything order-sensitive consumes
strictly in corpus order; the fluid prefix (INITIALIZING/CURING) stays serial.
"""

import threading
import time
from unittest.mock import MagicMock, patch

import pytest

from knowledge_graph_foundry.models import Entity, Ontology, TypeDef
from knowledge_graph_foundry.pipeline import Foundry
from knowledge_graph_foundry.settings import CuringSettings, ExtractionSettings, Settings


def _files(tmp_path, names):
    for n in names:
        (tmp_path / n).write_text(f"content of {n}")


def _foundry(store: dict, document_concurrency: int, cure: bool = False) -> Foundry:
    curing = (
        CuringSettings()
        if cure
        else CuringSettings(min_documents=50, max_fluid_documents=100)  # never cure
    )
    settings = Settings(
        curing=curing,
        extraction=ExtractionSettings(document_concurrency=document_concurrency),
    )
    f = Foundry(settings)
    f._driver = MagicMock()
    f._load_state = lambda: dict(store)
    f._save_state = lambda state: store.update(state)
    return f


def _seed_state(store: dict, fsm_state: str = "STABLE") -> None:
    ontology = Ontology(purpose="test purpose")
    if fsm_state == "STABLE":
        ontology.cured = True
        ontology.types = {"Thing": TypeDef(name="Thing", status="cured")}
    store.update(
        {
            "fsm_state": fsm_state,
            "purpose": "test purpose",
            "ontology": ontology.model_dump(),
        }
    )


class _TrackingExtract:
    """Extraction stub tracking per-doc call order and peak concurrency."""

    def __init__(self, sleep: float = 0.05, fail_on: str | None = None):
        self.sleep = sleep
        self.fail_on = fail_on
        self.calls: list[str] = []
        self.in_flight = 0
        self.peak = 0
        self._lock = threading.Lock()

    def __call__(self, path, purpose, ontology):
        with self._lock:
            self.in_flight += 1
            self.peak = max(self.peak, self.in_flight)
            self.calls.append(path.name)
        try:
            time.sleep(self.sleep)
            if self.fail_on and path.name == self.fail_on:
                raise ValueError("corrupt document")
            return (
                [Entity.create(f"entity-{path.name}", types=["Thing"], description="x")],
                [],
            )
        finally:
            with self._lock:
                self.in_flight -= 1


@pytest.fixture
def lease_patches():
    with (
        patch("knowledge_graph_foundry.graph.lock.acquire_lease", return_value=True),
        patch("knowledge_graph_foundry.graph.lock.heartbeat", return_value=True),
        patch("knowledge_graph_foundry.graph.lock.release_lease"),
    ):
        yield


def test_default_is_serial():
    assert ExtractionSettings().document_concurrency == 1


class TestStablePrefetch:
    def _run(self, tmp_path, dc: int, extract: _TrackingExtract, names=None):
        names = names or ["a.txt", "b.txt", "c.txt", "d.txt", "e.txt"]
        _files(tmp_path, names)
        store: dict = {}
        _seed_state(store, "STABLE")
        f = _foundry(store, document_concurrency=dc)
        f._extract_file = extract
        f._embed = lambda e: e
        consumed: list[int] = []

        def stable_load(entities, relationships, ontology, calibrator):
            consumed.append(entities[0].name)
            return 0.0, 0

        f._stable_load = stable_load
        summary = f.ingest(tmp_path)
        return summary, store, consumed

    def test_prefetch_overlaps_extraction_in_stable(self, tmp_path, lease_patches):
        extract = _TrackingExtract()
        summary, store, consumed = self._run(tmp_path, dc=3, extract=extract)
        assert summary["documents"] == 5
        assert extract.peak >= 2  # extractions genuinely overlapped
        # order-sensitive consumption stays strict corpus order
        assert consumed == [f"entity-{n}" for n in ["a.txt", "b.txt", "c.txt", "d.txt", "e.txt"]]
        assert store["documents_processed"] == 5

    def test_serial_default_never_overlaps(self, tmp_path, lease_patches):
        extract = _TrackingExtract()
        summary, _, _ = self._run(tmp_path, dc=1, extract=extract)
        assert summary["documents"] == 5
        assert extract.peak == 1

    def test_failed_document_skipped_others_survive(self, tmp_path, lease_patches):
        extract = _TrackingExtract(fail_on="c.txt")
        summary, store, consumed = self._run(tmp_path, dc=3, extract=extract)
        assert summary["documents"] == 4
        assert "entity-c.txt" not in consumed
        assert store["documents_processed"] == 4

    def test_resume_skips_prefetched_completions(self, tmp_path, lease_patches):
        extract = _TrackingExtract()
        _, store, _ = self._run(tmp_path, dc=3, extract=extract)
        # second run over the same corpus: fingerprints all recorded, no re-extraction
        f2 = _foundry(store, document_concurrency=3)
        f2._extract_file = MagicMock()
        f2._embed = lambda e: e
        f2._stable_load = lambda e, r, o, c: (0.0, 0)
        assert f2.ingest(tmp_path)["documents"] == 0
        f2._extract_file.assert_not_called()


class TestFluidStaysSerial:
    def test_curing_prefix_ignores_the_knob(self, tmp_path, lease_patches):
        _files(tmp_path, ["a.txt", "b.txt", "c.txt", "d.txt"])
        store: dict = {}
        _seed_state(store, "INITIALIZING")
        extract = _TrackingExtract()
        f = _foundry(store, document_concurrency=4)
        f._extract_file = extract
        f._embed = lambda e: e
        summary = f.ingest(tmp_path)
        assert summary["documents"] == 4
        assert extract.peak == 1  # fluid phase: ontology evolves per doc, serial
