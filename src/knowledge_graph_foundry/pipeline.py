"""Foundry pipeline - wires ingest -> extract -> resolve -> load per
lifecycle phase. The graph metanode is the single source of truth: every
public operation restores state from it first and persists back after.
"""

from __future__ import annotations

import hashlib
import json
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import re
from typing import Optional

from loguru import logger

from knowledge_graph_foundry.drift import DriftDetector, adopt_drifted_types
from knowledge_graph_foundry.engines import Engine, create_engine
from knowledge_graph_foundry.events import emit
from knowledge_graph_foundry.fsm import Lifecycle
from knowledge_graph_foundry.graphdb import create_driver
from knowledge_graph_foundry.ingest.chunking import chunk_document
from knowledge_graph_foundry.ingest.readers import (
    is_structured,
    iter_source_files,
    read_document,
    read_structured,
    row_document,
    text_heavy_columns,
)
from knowledge_graph_foundry.models import Document, Entity, Ontology, Relationship
from knowledge_graph_foundry.ontology.buffer import FluidBuffer
from knowledge_graph_foundry.ontology.clustering import (
    apply_type_remap,
    cluster_types,
    demote_value_types,
)
from knowledge_graph_foundry.ontology.curing import CuringDetector
from knowledge_graph_foundry.ontology.metrics import StabilityMetrics
from knowledge_graph_foundry.ontology.seed import load_seed
from knowledge_graph_foundry.resolution import (
    PosteriorCalibrator,
    evidence,
    remap_relationships,
    resolve_entities,
)
from knowledge_graph_foundry.settings import Settings, load_settings


class FoundryError(RuntimeError):
    pass


class Foundry:
    def __init__(self, settings: Optional[Settings] = None):
        # Zero-arg use is the simplest form: settings load from config.yml (if
        # present) with .env / environment overrides. Pass a Settings to
        # configure anything explicitly.
        self.settings = settings if settings is not None else load_settings()
        self._driver = None
        self._engine: Optional[Engine] = None
        self._extraction_engine: Optional[Engine] = None

    @classmethod
    def from_config(cls, config_path: Optional[Path] = None) -> "Foundry":
        """Build a Foundry from a config.yml (env overrides applied)."""
        from knowledge_graph_foundry.settings import load_settings

        return cls(load_settings(config_path))

    def __enter__(self) -> "Foundry":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # -- lazy resources -------------------------------------------------

    @property
    def driver(self):
        if self._driver is None:
            self._driver = create_driver(self.settings.neo4j)
        return self._driver

    @property
    def engine(self) -> Engine:
        """The orchestrator/reasoning engine (clustering, judging, query)."""
        if self._engine is None:
            self._engine = create_engine(self.settings.llm)
        return self._engine

    @property
    def extraction_engine(self) -> Engine:
        """The extraction engine; falls back to the orchestrator when
        extraction_llm is not configured (R9 role-based routing)."""
        if self.settings.extraction_llm is None:
            return self.engine
        if self._extraction_engine is None:
            self._extraction_engine = create_engine(self.settings.extraction_llm)
        return self._extraction_engine

    def close(self) -> None:
        if self._driver is not None:
            self._driver.close()
            self._driver = None

    # -- state ----------------------------------------------------------

    def _load_state(self) -> dict:
        from knowledge_graph_foundry.graph.metanode import read_control

        return read_control(self.driver) or {}

    def _save_state(self, state: dict) -> None:
        from knowledge_graph_foundry.graph.metanode import write_control

        write_control(self.driver, state)

    def _make_calibrator(self, state: dict) -> Optional[PosteriorCalibrator]:
        """Load the resolver's calibrator. A per-corpus frozen artifact
        (resolution.calibration_path, H157/H142) wins when present; otherwise
        the calibration persisted in graph state; otherwise none (fixed
        threshold)."""
        path = self.settings.resolution.calibration_path
        if path and Path(path).exists():
            return PosteriorCalibrator.from_json(Path(path).read_text())
        if state.get("calibration"):
            return PosteriorCalibrator.from_json(state["calibration"])
        return None

    def _gate_threshold(self) -> float:
        """R38-H384 two-tier escalation cut: a frozen per-corpus file artifact
        wins; else the graph-persisted record (fingerprint-checked against the
        pile it was fitted on); else the a-priori settings prior. Fitted cuts
        are corpus-class-bound (H157) - a record fitted on a different pile
        falls back to the prior instead of transferring silently."""
        from knowledge_graph_foundry.graph.gate_calibration import corpus_fingerprint

        path = self.settings.graphrag.gate_calibration_path
        if path and Path(path).exists():
            return float(json.loads(Path(path).read_text())["threshold"])
        state = self._load_state()
        record = state.get("gate_calibration")
        if record:
            fp = corpus_fingerprint(state.get("processed_documents") or [])
            rec_fp = (record.get("provenance") or {}).get("corpus_fingerprint")
            if rec_fp and rec_fp != fp:
                logger.warning(
                    f"gate_calibration fingerprint mismatch ({rec_fp} != {fp}) - using prior"
                )
                return self.settings.graphrag.escalation_threshold_prior
            return float(record["threshold"])
        return self.settings.graphrag.escalation_threshold_prior

    def _materialize_soft_links(self, decisions, id_map: dict[str, str]) -> None:
        """R15-H268: turn resolver defer-zone decisions into posterior-weighted
        SIMILAR_TO soft links (link, never merge). Ids are remapped through the
        resolution id map so an endpoint merged elsewhere still links correctly."""
        from knowledge_graph_foundry.graph.densify import add_soft_links

        pairs: list[tuple[str, str, float]] = []
        for d in decisions:
            if d.decision != "defer":
                continue
            left = id_map.get(d.left_id, d.left_id)
            right = id_map.get(d.right_id, d.right_id)
            if left != right:
                pairs.append((left, right, d.posterior))
        if pairs:
            add_soft_links(self.driver, pairs)

    # -- operations -------------------------------------------------------

    def init_project(self, purpose: str, seed: Optional[str] = None) -> Ontology:
        """Create the control metanode with purpose and optional seed."""
        state = self._load_state()
        if state.get("fsm_state") and state["fsm_state"] != "EMPTY":
            raise FoundryError(
                f"project already initialized (state {state['fsm_state']}); use wipe first"
            )
        seed_source: Path | str | None = seed
        if seed and Path(seed).exists():
            seed_source = Path(seed)
        ontology = load_seed(seed_source, purpose, engine=self.engine if seed else None)
        lifecycle = Lifecycle("EMPTY")
        lifecycle.initialize()
        self._save_state(
            {
                "fsm_state": lifecycle.state,
                "purpose": purpose,
                "ontology": ontology.model_dump(),
                "buffer_cache": None,
                "metrics_history": None,
                "calibration": None,
                "drift": None,
            }
        )
        return ontology

    def repurpose(self, purpose: str, seed: Optional[str] = None) -> dict:
        """Change the graph's use case in place - the long-lived-graph answer to
        an owner changing their mind about what the graph is for. The old purpose
        is appended to purpose_history (the objective is bitemporal too); future
        ingestion and repair extract under the new purpose. An optional seed
        merges additional protected types into the live ontology without
        touching existing ones. Requires a STABLE graph; no re-ingest."""
        from datetime import datetime, timezone

        state = self._load_state()
        if not state or state.get("fsm_state") != "STABLE":
            raise FoundryError("repurpose requires a STABLE graph")
        old_purpose = state.get("purpose", "")
        if purpose == old_purpose:
            raise FoundryError("new purpose is identical to the current one")
        history = state.get("purpose_history") or []
        history.append(
            {
                "purpose": old_purpose,
                "replaced_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        ontology = Ontology(**state["ontology"]) if state.get("ontology") else Ontology()
        ontology.purpose = purpose
        seeded_added: list[str] = []
        if seed:
            seed_source: Path | str = Path(seed) if Path(seed).exists() else seed
            seeded = load_seed(seed_source, purpose, engine=self.engine)
            for name, tdef in seeded.types.items():
                if name not in ontology.types:
                    ontology.types[name] = tdef
                    seeded_added.append(name)
        state.update(
            {
                "purpose": purpose,
                "purpose_history": history,
                "ontology": ontology.model_dump(),
            }
        )
        self._save_state(state)
        return {
            "purpose": purpose,
            "previous_purpose": old_purpose,
            "purpose_changes": len(history),
            "seeded_types_added": seeded_added,
        }

    def status(self) -> dict:
        state = self._load_state()
        if not state:
            return {"fsm_state": "EMPTY"}
        with self.driver.session() as session:
            counts = session.run(
                "MATCH (e:Entity) WITH count(e) AS entities "
                "OPTIONAL MATCH (:Entity)-[r]->(:Entity) "
                "RETURN entities, count(r) AS relationships"
            ).single()
        ontology = Ontology(**state["ontology"]) if state.get("ontology") else Ontology()
        metrics_history = state.get("metrics_history") or []
        return {
            "fsm_state": state.get("fsm_state", "EMPTY"),
            "purpose": state.get("purpose", ""),
            "entities": counts["entities"],
            "relationships": counts["relationships"],
            "types": sorted(ontology.types),
            "cured": ontology.cured,
            "documents_processed": state.get("documents_processed", 0),
            "latest_metrics": metrics_history[-1] if metrics_history else None,
            "drift": state.get("drift_verdict"),
        }

    def ingest(self, path: "str | Path") -> dict:
        """Ingest a file, directory or zip through the full lifecycle.

        Exactly one ingester may run at a time: the run claims a
        graph-resident lease first (see graph/lock.py) and heartbeats it
        after every document; a concurrent ingest fails fast naming the
        holder, and a stale lease from a crashed run is reclaimed."""
        from knowledge_graph_foundry.graph.lock import (
            acquire_lease,
            lease_holder,
            new_run_id,
            release_lease,
        )

        path = Path(path)
        run_id = new_run_id()
        if not acquire_lease(self.driver, run_id, self.settings.lease_ttl_seconds):
            holder = lease_holder(self.driver) or {}
            raise FoundryError(
                "another ingestion run holds the lease "
                f"(holder {holder.get('holder', '?')}, run {holder.get('run_id', '?')}, "
                f"last heartbeat {holder.get('age_seconds', 0):.0f}s ago); "
                "wait for it to finish or let a stale lease expire"
            )
        try:
            return self._ingest_locked(path, run_id)
        finally:
            release_lease(self.driver, run_id)

    def _ingest_locked(self, path: Path, run_id: str) -> dict:
        from knowledge_graph_foundry.graph.lock import heartbeat

        state = self._load_state()
        if not state or not state.get("fsm_state") or state["fsm_state"] == "EMPTY":
            raise FoundryError("project not initialized - run `kgf init` first")

        lifecycle = Lifecycle(state["fsm_state"])
        purpose = state.get("purpose", "")
        ontology = Ontology(**state["ontology"])
        curing_cfg = self.settings.curing

        buffer: Optional[FluidBuffer] = None
        metrics = StabilityMetrics()
        detector = CuringDetector(curing_cfg)
        drift: Optional[DriftDetector] = None
        calibrator = self._make_calibrator(state)

        if lifecycle.state in ("INITIALIZING", "CURING"):
            if state.get("buffer_cache"):
                buffer = FluidBuffer.from_dict(state["buffer_cache"], curing_cfg)
                ontology = buffer.ontology
            else:
                buffer = FluidBuffer(ontology, curing_cfg)
            if state.get("metrics_history"):
                metrics = StabilityMetrics.from_dict({"history": state["metrics_history"]})
                detector = CuringDetector.from_dict(
                    {"records": state["metrics_history"]}, curing_cfg
                )
        elif lifecycle.state in ("STABLE", "RECURING"):
            if state.get("drift"):
                drift = DriftDetector.from_dict(state["drift"], self.settings.drift)
            else:
                drift = DriftDetector(self.settings.drift, self._cured_frequencies(ontology))

        files = iter_source_files(Path(path))
        if not files:
            raise FoundryError(f"no supported files found under {path}")

        summary = {"documents": 0, "entities": 0, "relationships": 0, "cured": ontology.cured}
        documents_processed = state.get("documents_processed", 0)
        # resume contract: name+content fingerprints of completed documents;
        # a killed run skips what it finished, a REVISED file (same name, new
        # content) gets a new fingerprint and is re-ingested (S2 drift flow)
        processed_documents = set(state.get("processed_documents", []))
        state_drift = None

        # DEF-12/R30-H343: cross-document extraction look-ahead. Extraction is
        # pure (doc, purpose, ontology) -> (entities, relationships), so in
        # STABLE/RECURING - where the cured ontology is loop-invariant - up to
        # document_concurrency extractions run ahead of the consumer, while
        # everything order-sensitive (curing, drift, resolution, graph write,
        # state save, resume fingerprints) consumes strictly in corpus order.
        # While fluid (INITIALIZING/CURING) the ontology evolves per document,
        # so that prefix stays serial regardless of the knob.
        doc_concurrency = max(1, self.settings.extraction.document_concurrency)

        def unit_stream():
            for stream_path in files:
                # DEF-2: a text-heavy structured file expands to one unit per row,
                # each its own document; everything else is one whole-file unit
                try:
                    units = self._document_units(stream_path)
                except Exception as exc:  # corrupt file: skip, continue run
                    emit("document.skipped", path=str(stream_path), reason=str(exc))
                    logger.warning(f"skipping {stream_path}: {exc}")
                    continue
                for unit_fingerprint, unit_row_doc in units:
                    if unit_fingerprint in processed_documents:
                        emit("document.skipped", path=str(stream_path), reason="already ingested")
                        continue
                    yield stream_path, unit_fingerprint, unit_row_doc

        def extract_unit(unit_path, unit_row_doc, unit_ontology):
            if unit_row_doc is not None:
                return self._extract_text_document(
                    unit_row_doc,
                    f"{unit_path.name}#row{unit_row_doc.metadata['row_index']}",
                    purpose,
                    unit_ontology,
                )
            return self._extract_file(unit_path, purpose, unit_ontology)

        stream = unit_stream()
        pending: deque = deque()
        pool = (
            ThreadPoolExecutor(max_workers=doc_concurrency, thread_name_prefix="kgf-doc")
            if doc_concurrency > 1
            else None
        )
        try:
            while True:
                if pool is not None and lifecycle.state in ("STABLE", "RECURING"):
                    while len(pending) < doc_concurrency:
                        nxt = next(stream, None)
                        if nxt is None:
                            break
                        ahead_path, ahead_fingerprint, ahead_row_doc = nxt
                        emit("document.started", path=str(ahead_path))
                        pending.append(
                            (
                                pool.submit(extract_unit, ahead_path, ahead_row_doc, ontology),
                                ahead_path,
                                ahead_fingerprint,
                            )
                        )
                    if not pending:
                        break
                    future, file_path, fingerprint = pending.popleft()
                    try:
                        entities, relationships = future.result()
                    except Exception as exc:  # corrupt file: skip, continue run
                        emit("document.skipped", path=str(file_path), reason=str(exc))
                        logger.warning(f"skipping {file_path}: {exc}")
                        continue
                else:
                    nxt = next(stream, None)
                    if nxt is None:
                        break
                    file_path, fingerprint, row_doc = nxt
                    emit("document.started", path=str(file_path))
                    try:
                        entities, relationships = extract_unit(file_path, row_doc, ontology)
                    except Exception as exc:  # corrupt file: skip, continue run
                        emit("document.skipped", path=str(file_path), reason=str(exc))
                        logger.warning(f"skipping {file_path}: {exc}")
                        continue

                if not entities:
                    emit("document.skipped", path=str(file_path), reason="no entities")
                    continue

                entities = self._embed(entities)
                processed_documents.add(fingerprint)
                documents_processed += 1
                summary["documents"] += 1
                summary["entities"] += len(entities)
                summary["relationships"] += len(relationships)

                if lifecycle.state in ("INITIALIZING", "CURING"):
                    if lifecycle.state == "INITIALIZING":
                        lifecycle.start_curing()
                    buffer.add_document(entities, relationships)
                    ontology = buffer.ontology
                    record = metrics.record(buffer.type_frequencies())
                    detector.record(record)
                    should_cure, reason = detector.should_cure()
                    if should_cure:
                        ontology, drift = self._consolidate(buffer, purpose, calibrator, reason)
                        lifecycle.cure()
                        summary["cured"] = True
                        buffer = None
                else:
                    remap_rate, invalidated = self._stable_load(
                        entities, relationships, ontology, calibrator
                    )
                    verdict = drift.record_document(remap_rate, self._frequencies(entities))
                    fact_verdict = drift.record_contradictions(invalidated, len(entities))
                    if verdict.action == "recure":
                        lifecycle.recure()
                        drift.begin_recure()
                    elif lifecycle.state == "RECURING" and drift.recure_ready():
                        # R36-H378/DEF-9: bounded RECURING exit - adopt the
                        # drifted register's sustained types (patch tier),
                        # re-baseline the detector, walk back to STABLE
                        window = drift.recure_window_frequencies()
                        adopted = adopt_drifted_types(
                            ontology, window, self.settings.drift.recure_adopt_share
                        )
                        drift.end_recure(window)
                        lifecycle.cure()
                        emit("drift.recure_completed", adopted=adopted)
                    state_drift = fact_verdict.action if fact_verdict else verdict.action

                # persist after EVERY document - resumability is the contract;
                # the heartbeat keeps the lease live and detects a takeover
                if not heartbeat(self.driver, run_id):
                    raise FoundryError(
                        "ingest lease lost mid-run (stale takeover) - aborting to avoid "
                        "concurrent state mutation; state through the previous document is persisted"
                    )
                self._save_state(
                    {
                        "fsm_state": lifecycle.state,
                        "purpose": purpose,
                        "ontology": ontology.model_dump(),
                        "buffer_cache": buffer.to_dict() if buffer else None,
                        "metrics_history": metrics.history() if buffer else None,
                        "calibration": calibrator.to_json() if calibrator else None,
                        "drift": drift.to_dict() if drift else None,
                        "documents_processed": documents_processed,
                        "processed_documents": sorted(processed_documents),
                        "drift_verdict": state_drift if lifecycle.state == "STABLE" else None,
                    }
                )
                emit("document.completed", path=str(file_path), entities=len(entities))
        finally:
            if pool is not None:
                pool.shutdown(wait=False, cancel_futures=True)

        # DEF-7: corpus exhausted while still fluid - the gate never fired, so the
        # buffer would outlive the ingest and the graph would stay entity-less;
        # consolidate on whatever evidence the corpus provided
        if buffer is not None and buffer.documents_processed > 0:
            ontology, drift = self._consolidate(buffer, purpose, calibrator, "corpus_exhausted")
            lifecycle.cure()
            summary["cured"] = True
            buffer = None
            self._save_state(
                {
                    "fsm_state": lifecycle.state,
                    "purpose": purpose,
                    "ontology": ontology.model_dump(),
                    "buffer_cache": None,
                    "metrics_history": None,
                    "calibration": calibrator.to_json() if calibrator else None,
                    "drift": drift.to_dict() if drift else None,
                    "documents_processed": documents_processed,
                    "processed_documents": sorted(processed_documents),
                    "drift_verdict": None,
                }
            )

        emit("load.completed", **summary)
        return summary

    # -- internals --------------------------------------------------------

    def _extract_file(
        self, file_path: Path, purpose: str, ontology: Ontology
    ) -> tuple[list[Entity], list[Relationship]]:
        from knowledge_graph_foundry.extraction import (
            apply_mapping,
            structured_mapping,
        )

        if is_structured(file_path):
            rows = read_structured(file_path)
            if not rows:
                return [], []
            mapping = structured_mapping(rows[:5], purpose, self.engine)
            result = apply_mapping(rows, mapping, document_id=f"d_{file_path.stem}")
            return result.entities, result.relationships
        document = read_document(
            file_path,
            parser_union=self.settings.extraction.parser_union,
            glyph_normalization=self.settings.extraction.glyph_normalization,
        )
        return self._extract_text_document(document, file_path.name, purpose, ontology)

    def _extract_text_document(
        self, document: Document, source_name: str, purpose: str, ontology: Ontology
    ) -> tuple[list[Entity], list[Relationship]]:
        """Chunk-and-extract one Document - the unstructured path shared by
        whole files and text-heavy structured rows (DEF-2)."""
        from knowledge_graph_foundry.extraction import extract_document

        chunks = chunk_document(
            document,
            chunk_size=self.settings.extraction.chunk_size,
            chunk_overlap=self.settings.extraction.chunk_overlap,
            header_carryover=self.settings.extraction.header_carryover,
        )
        if not chunks:
            return [], []
        result = extract_document(
            chunks,
            purpose,
            ontology,
            self.extraction_engine,
            concurrency=self.settings.extraction.concurrency,
            extraction_cfg=self.settings.extraction,
        )
        if self.settings.load.provenance_nodes:
            self._load_provenance(document, chunks, source_name)
        return result.entities, result.relationships

    def _document_units(self, file_path: Path) -> "list[tuple[str, Optional[Document]]]":
        """Expand a source file into resumable (fingerprint, document) units.

        DEF-2: a structured file with a text-heavy column (median cell length
        above ingest.text_column_median_chars) yields one unit PER ROW - each
        row is its own document with its own resume fingerprint and its own
        curing contribution, so the prose actually reaches the LLM. Everything
        else stays one whole-file unit (document None) extracted as before."""
        if is_structured(file_path):
            rows = read_structured(file_path)
            columns = text_heavy_columns(rows, self.settings.ingest.text_column_median_chars)
            if columns:
                units: list[tuple[str, Optional[Document]]] = []
                for index, row in enumerate(rows):
                    digest = hashlib.sha1(
                        json.dumps(row, sort_keys=True, default=str).encode()
                    ).hexdigest()[:16]
                    units.append(
                        (
                            f"{file_path.name}#row{index}:{digest}",
                            row_document(file_path, row, index, columns),
                        )
                    )
                return units
        return [
            (
                f"{file_path.name}:{hashlib.sha1(file_path.read_bytes()).hexdigest()[:16]}",
                None,
            )
        ]

    def repair(self, question: str, sources: "list[str | Path]") -> dict:
        """R04 targeted repair: a failing question names its source documents;
        re-extract them with the question as extraction focus and load the new
        facts into the live graph. Deliberately bypasses the resume fingerprint
        skip (repair re-reads on purpose); requires a STABLE graph."""
        from knowledge_graph_foundry.graph.lock import acquire_lease, new_run_id, release_lease
        from knowledge_graph_foundry.graph.propositions import generate_propositions

        state = self._load_state()
        if not state or state.get("fsm_state") != "STABLE":
            raise FoundryError("repair requires a STABLE graph")
        purpose = state.get("purpose", "")
        ontology = Ontology(**state["ontology"])
        calibrator = self._make_calibrator(state)
        focused = f"{purpose}\nRepair focus - extract the facts that answer: {question}"

        run_id = new_run_id()
        if not acquire_lease(self.driver, run_id, self.settings.lease_ttl_seconds):
            raise FoundryError("another ingestion run holds the lease")
        summary = {"documents": 0, "entities": 0, "relationships": 0, "invalidated": 0}
        try:
            for source in sources:
                path = Path(source)
                emit("document.started", path=str(path), repair=True)
                entities, relationships = self._extract_file(path, focused, ontology)
                if not entities:
                    emit("document.skipped", path=str(path), reason="no entities")
                    continue
                entities = self._embed(entities)
                _, invalidated = self._stable_load(entities, relationships, ontology, calibrator)
                summary["documents"] += 1
                summary["entities"] += len(entities)
                summary["relationships"] += len(relationships)
                summary["invalidated"] += invalidated
                emit("document.completed", path=str(path), entities=len(entities), repair=True)
            if self.settings.graphrag.propositions_enabled and summary["entities"]:
                summary["propositions"] = generate_propositions(
                    self.driver,
                    self._embed_texts,
                    self.settings.graphrag.proposition_index_name,
                    self.settings.graphrag.vector_dimensions,
                    split_max_tokens=self.settings.graphrag.proposition_split_max_tokens,
                )
        finally:
            release_lease(self.driver, run_id)
        return summary

    def _load_provenance(self, document, chunks, source_name: str) -> None:
        """R02-H12/S6: persist Document + Chunk nodes so passages join the PPR
        projection and every entity is traceable to its source text."""
        with self.driver.session() as session:
            session.run(
                "MERGE (d:KGFDocument {id: $id}) "
                "ON CREATE SET d.name = $name, d.created_at = timestamp()",
                id=document.id,
                name=source_name,
            ).consume()
            session.run(
                "UNWIND $rows AS row "
                "MERGE (c:Chunk {id: row.id}) "
                "ON CREATE SET c.text = row.text, c.index = row.index, "
                "c.created_at = timestamp() "
                "WITH c MATCH (d:KGFDocument {id: $doc_id}) "
                "MERGE (c)-[:PART_OF]->(d)",
                rows=[{"id": c.id, "text": c.text, "index": i} for i, c in enumerate(chunks)],
                doc_id=document.id,
            ).consume()

    def _embed(self, entities: list[Entity]) -> list[Entity]:
        from knowledge_graph_foundry.extraction import generate_embeddings

        try:
            return generate_embeddings(entities, self.settings.embeddings)
        except Exception as exc:
            logger.warning(f"embeddings unavailable, continuing without: {exc}")
            return entities

    def _embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Embed raw texts (for R5 type clustering) via the embeddings module."""
        from knowledge_graph_foundry.extraction import generate_embeddings

        probes = [
            Entity.create(f"t{i}", types=["Type"], description=t) for i, t in enumerate(texts)
        ]
        embedded = generate_embeddings(probes, self.settings.embeddings)
        return [e.embedding or [] for e in embedded]

    def _consolidate(
        self,
        buffer: FluidBuffer,
        purpose: str,
        calibrator: Optional[PosteriorCalibrator],
        reason: str,
    ) -> tuple[Ontology, DriftDetector]:
        """Cure: cluster types once, resolve the whole buffer, flush to Neo4j."""
        from knowledge_graph_foundry.graph.loader import (
            ensure_indexes,
            load_entities,
            load_relationships,
        )

        ontology = buffer.ontology
        demotion_remap: dict[str, str] = {}
        curing_cfg = self.settings.curing
        if curing_cfg.value_type_demotion:
            member_names: dict[str, list[str]] = {}
            for e in buffer.entities:
                for t in e.types:
                    member_names.setdefault(t, []).append(e.name)
            ontology, demotion_remap = demote_value_types(
                ontology,
                member_names,
                fraction=curing_cfg.value_type_fraction,
                target=curing_cfg.value_type_target,
            )
        ontology, type_remap = cluster_types(
            ontology, purpose, self.engine, embed_fn=self._embed_texts
        )
        entities = [
            e.model_copy(
                update={
                    "types": apply_type_remap(
                        apply_type_remap(e.types, demotion_remap), type_remap
                    )
                }
            )
            for e in buffer.entities
        ]
        result = resolve_entities(
            entities,
            self.settings.resolution,
            calibrator,
            engine=self.engine,
            glyph_normalization=self.settings.extraction.glyph_normalization,
        )
        relationships = remap_relationships(buffer.relationships, result.id_map)

        ensure_indexes(
            self.driver,
            vector_dimensions=self.settings.graphrag.vector_dimensions,
            vector_index_name=self.settings.graphrag.vector_index_name,
        )
        load_entities(
            self.driver,
            result.entities,
            batch_size=self.settings.load.batch_size,
            versioning=self.settings.load.entity_versioning,
        )
        load_relationships(self.driver, relationships, batch_size=self.settings.load.batch_size)
        self._reconcile(relationships)
        if self.settings.resolution.soft_links:
            self._materialize_soft_links(result.decisions, result.id_map)

        ontology.cured = True
        emit(
            "curing.cured" if reason != "forced" else "curing.forced",
            reason=reason,
            documents=buffer.documents_processed,
            types=len(ontology.types),
            entities=len(result.entities),
        )
        drift = DriftDetector(self.settings.drift, self._cured_frequencies(ontology))
        return ontology, drift

    def _stable_load(
        self,
        entities: list[Entity],
        relationships: list[Relationship],
        ontology: Ontology,
        calibrator: Optional[PosteriorCalibrator],
    ) -> tuple[float, int]:
        """Resolve one post-cure document against the live graph and load it.
        Returns (remap_rate, invalidated) - the fraction of entities typed
        outside the cured ontology (schema drift) and the count of edges
        superseded by reconciliation (fact drift)."""
        from knowledge_graph_foundry.graph.graphrag import vector_query
        from knowledge_graph_foundry.graph.loader import load_entities, load_relationships

        result = resolve_entities(
            entities,
            self.settings.resolution,
            calibrator,
            engine=self.engine,
            glyph_normalization=self.settings.extraction.glyph_normalization,
        )
        id_map = dict(result.id_map)

        # Bayesian match against live graph candidates via the vector index
        for entity in result.entities:
            if not entity.embedding:
                continue
            try:
                candidates = vector_query(
                    self.driver,
                    entity.embedding,
                    self.settings.graphrag.vector_index_name,
                    top_k=3,
                )
            except Exception:
                break  # index not ready - identity merge by id still applies
            for candidate in candidates:
                if candidate["id"] == entity.id:
                    continue
                graph_entity = Entity(
                    id=candidate["id"],
                    name=candidate["name"],
                    types=candidate.get("types", []),
                    description=candidate.get("description", "") or "",
                )
                decision = evidence(entity, graph_entity, self.settings.resolution)
                if self.settings.resolution.identity_stack == "v2":
                    from knowledge_graph_foundry.resolution.resolver import _v2_stack

                    stack = _v2_stack(self.settings.resolution)
                    contra = stack.nli_contra_batch([(entity, graph_entity)])[0]
                    # Neo4j cosine index score is (1 + cos) / 2 - invert it
                    cosine = 2.0 * candidate["score"] - 1.0
                    verdict, score, vetoed = stack.decide(
                        entity, graph_entity, decision.posterior, contra, cosine=cosine
                    )
                    decision = decision.model_copy(
                        update={"posterior": score, "decision": verdict}
                    )
                    if vetoed:
                        emit(
                            "resolution.veto",
                            left_id=entity.id,
                            right_id=graph_entity.id,
                            nli_contra=contra,
                        )
                emit(f"resolution.{decision.decision}", **decision.model_dump())
                if decision.decision == "merge":
                    id_map[entity.id] = graph_entity.id
                    entity = entity.model_copy(update={"id": graph_entity.id})
                    break

        merged_entities = [
            e.model_copy(update={"id": id_map.get(e.id, e.id)}) for e in result.entities
        ]
        merged_relationships = remap_relationships(relationships, id_map)
        load_entities(
            self.driver,
            merged_entities,
            batch_size=self.settings.load.batch_size,
            versioning=self.settings.load.entity_versioning,
        )
        load_relationships(
            self.driver, merged_relationships, batch_size=self.settings.load.batch_size
        )
        invalidated = self._reconcile(merged_relationships)
        if self.settings.resolution.soft_links:
            self._materialize_soft_links(result.decisions, id_map)

        unknown = sum(1 for e in merged_entities if not any(t in ontology.types for t in e.types))
        remap_rate = unknown / len(merged_entities) if merged_entities else 0.0
        return remap_rate, invalidated

    def _reconcile(self, relationships: list[Relationship]) -> int:
        """Invalidate prior functional edges superseded by these; returns the
        contradiction count (fed to fact-drift monitoring)."""
        functional = self.settings.load.functional_relationship_types
        if not functional:
            return 0
        from knowledge_graph_foundry.graph.temporal import reconcile_contradictions

        return reconcile_contradictions(self.driver, relationships, functional)

    def _frequencies(self, entities: list[Entity]) -> dict[str, int]:
        freqs: dict[str, int] = {}
        for entity in entities:
            for t in entity.types:
                freqs[t] = freqs.get(t, 0) + 1
        return freqs

    def _cured_frequencies(self, ontology: Ontology) -> dict[str, int]:
        return {name: t.encounters for name, t in ontology.types.items()}

    # -- graphrag ---------------------------------------------------------

    def optimize(self) -> dict:
        from knowledge_graph_foundry.graph.graphrag import (
            detect_communities,
            scorecard,
            summarize_communities,
        )

        communities = detect_communities(self.driver, self.settings.graphrag.community_min_size)
        summaries = 0
        if not communities.get("skipped"):
            summaries = summarize_communities(
                self.driver, self.engine, self.settings.graphrag.community_min_size
            )
        spec_hoist = None
        if self.settings.resolution.spec_hoist:
            from knowledge_graph_foundry.graph.hoist import (
                bridge_series_fragments,
                hoist_unanimous_specs,
            )

            bridged = bridge_series_fragments(self.driver)
            spec_hoist = {"bridged_edges": bridged, **hoist_unanimous_specs(self.driver)}
        propositions = 0
        if self.settings.graphrag.propositions_enabled:
            from knowledge_graph_foundry.graph.propositions import generate_propositions

            propositions = generate_propositions(
                self.driver,
                self._embed_texts,
                self.settings.graphrag.proposition_index_name,
                self.settings.graphrag.vector_dimensions,
                split_max_tokens=self.settings.graphrag.proposition_split_max_tokens,
            )
        passages = 0
        if self.settings.graphrag.passages_enabled:
            from knowledge_graph_foundry.extraction.embeddings import (
                channel_dimensions,
                embed_channel_texts,
            )
            from knowledge_graph_foundry.graph.passages import generate_passages

            ch = self.settings.embedding_channels.passages
            passages = generate_passages(
                self.driver,
                lambda texts: embed_channel_texts(texts, ch),
                self.settings.graphrag.passage_index_name,
                channel_dimensions(ch),
                ch.provider,
                ch.model,
                span_chars=self.settings.graphrag.passage_span_chars,
            )
        similarity_edges = 0
        if self.settings.graphrag.similarity_edges_enabled:
            from knowledge_graph_foundry.graph.densify import add_similarity_edges

            similarity_edges = add_similarity_edges(
                self.driver,
                self.settings.graphrag.vector_index_name,
                threshold=self.settings.graphrag.similarity_threshold,
                top_k=self.settings.graphrag.similarity_top_k,
            )
        court = None
        if self.settings.resolution.demotion_court:
            from knowledge_graph_foundry.graph.court import run_demotion_court

            court = run_demotion_court(self.driver, self.engine, self.settings.resolution)
        card = scorecard(self.driver)
        result = {
            "communities": communities,
            "summaries": summaries,
            "propositions": propositions,
            "passages": passages,
            "similarity_edges": similarity_edges,
            "spec_hoist": spec_hoist,
            "court": court,
            "scorecard": card,
        }
        self._persist_scorecard(result)
        return result

    def _persist_scorecard(self, result: dict) -> None:
        from datetime import datetime, timezone

        reports = Path("reports")
        if not reports.is_dir():
            return
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        path = reports / f"scorecard-{stamp}.json"
        path.write_text(json.dumps(result, indent=2, default=str))
        logger.info(f"scorecard saved to {path}")

    def query(self, question: str) -> dict:
        """Answer a question over the graph. Global/thematic questions use
        community summaries; entity and multi-hop questions use Personalized
        PageRank seeded from the vector top-k (R2/R6), with currently-valid
        neighbourhood context (R1 time-aware)."""
        from pydantic import BaseModel, Field

        from knowledge_graph_foundry.graph.graphrag import (
            global_summaries,
            is_global_query,
        )

        class Answer(BaseModel):
            answer: str
            supporting_entities: list[str] = Field(default_factory=list)

        if self.settings.graphrag.ppr_enabled and is_global_query(question):
            summaries = global_summaries(self.driver)
            if summaries:
                context = "\n\n".join(f"## {s['title']}\n{s['summary']}" for s in summaries)
                result = self.engine.complete(
                    [
                        {
                            "role": "system",
                            "content": "Answer from these knowledge-graph community summaries. "
                            "Say so if they do not cover the question.",
                        },
                        {"role": "user", "content": f"Question: {question}\n\n{context}"},
                    ],
                    Answer,
                )
                return {
                    "answer": result.answer,
                    "supporting_entities": result.supporting_entities,
                    "path": "global",
                }

        # R03-H15: comparisons decompose into per-entity retrievals, unioned
        from knowledge_graph_foundry.graph.graphrag import decompose_comparison

        sub_questions = (
            decompose_comparison(question)
            if self.settings.graphrag.decompose_comparisons
            else None
        )
        if sub_questions:
            context_lines, supporting = [], []
            coverage = {"top_score": 0.0}
            for sub in sub_questions:
                lines, names, cov = self._retrieve_local(sub)
                for line in lines:
                    if line not in context_lines:
                        context_lines.append(line)
                for name in names:
                    if name not in supporting:
                        supporting.append(name)
                coverage["top_score"] = max(coverage["top_score"], cov["top_score"])
                coverage["seed_top_score"] = max(
                    coverage.get("seed_top_score", 0.0), cov.get("seed_top_score", 0.0)
                )
                coverage["escalated"] = coverage.get("escalated", False) or cov.get(
                    "escalated", False
                )
            path = "ppr+decomposed"
        else:
            context_lines, supporting, coverage = self._retrieve_local(question)
            path = "ppr" if self.settings.graphrag.ppr_enabled else "vector"

        # R03-H17: structural abstention - do not generate over thin coverage
        if (
            self.settings.graphrag.abstention_enabled
            and coverage["top_score"] < self.settings.graphrag.abstention_min_score
        ):
            emit("query.abstained", question=question, **coverage)
            return {
                "answer": (
                    "The graph does not contain enough information to answer this "
                    f"question (best retrieval score {coverage['top_score']:.2f})."
                ),
                "supporting_entities": [],
                "path": "abstained",
            }

        result = self.engine.complete(
            [
                {
                    "role": "system",
                    "content": "Answer strictly from the provided knowledge graph context. "
                    "After each factual claim, cite the supporting entity in parentheses. "
                    "Name the entities supporting the answer. Say so when the graph lacks "
                    "the answer. Attribute a value to an entity ONLY when the context "
                    "explicitly states it for that entity - a value stated for a different "
                    "device, product or subject, or with no named subject, must not be "
                    "transferred to the one asked about; say the graph lacks it instead.",
                },
                {
                    "role": "user",
                    "content": f"Question: {question}\n\nGraph context:\n\n"
                    + "\n\n".join(context_lines),
                },
            ],
            Answer,
        )
        # R38-H385: the outcome side of the gate's label loop - the retrieval
        # twin of the resolution.* event bus (signal + outcome per query)
        emit(
            "query.answered",
            question=question,
            path=path,
            seed_top_score=coverage.get("seed_top_score", coverage["top_score"]),
            escalated=coverage.get("escalated", False),
            answer=result.answer,
            supporting_entities=result.supporting_entities or supporting,
        )
        return {
            "answer": result.answer,
            "supporting_entities": result.supporting_entities or supporting,
            "path": path,
        }

    def _retrieve_local(self, question: str) -> tuple[list[str], list[str], dict]:
        """Local retrieval: vector top-k seeds, expanded by PPR when enabled,
        each node rendered with its properties and currently-valid relations.
        Returns (context_lines, supporting_names, coverage) - coverage carries
        the structural signals the abstention gate reads (R03-H17)."""
        from knowledge_graph_foundry.extraction import generate_embeddings
        from knowledge_graph_foundry.graph.graphrag import (
            cap_fanout,
            detect_escalation,
            detect_miss,
            exclude_foreign_devices,
            fetch_entities,
            link_prop_values,
            overfetch_seeds,
            ppr_query,
            truncate_to_budget,
            vector_query,
        )

        probe = Entity.create(question[:80], types=["Query"], description=question)
        embedded = generate_embeddings([probe], self.settings.embeddings)
        qv = embedded[0].embedding
        # R15-H195a: over-fetch top_k*factor then truncate to top_k after ranking
        seeds = overfetch_seeds(
            lambda k: vector_query(
                self.driver, qv, self.settings.graphrag.vector_index_name, top_k=k
            ),
            self.settings.graphrag.top_k,
            self.settings.graphrag.overfetch_factor,
        )

        # R19-H181: on the miss class (best seed similarity below threshold) skip
        # the full render and return the cheap abstention form
        if self.settings.graphrag.miss_detector and detect_miss(
            seeds, self.settings.graphrag.miss_threshold
        ):
            top = max((s.get("score", 0.0) for s in seeds), default=0.0)
            nearest = ", ".join(s["name"] for s in seeds[:8])
            emit("query.miss", question=question, top_score=top)
            return (
                [f"No confident match. Nearest entities: {nearest}"],
                [s["name"] for s in seeds[:8]],
                {"top_score": top},
            )

        # R37-H382: sufficiency gate - decide once, on the pure top-seed
        # signal, whether this query's render escalates beyond rung 0; the
        # escalation band sits above the miss class ([miss, gate) never fires)
        seed_top = max((s.get("score", 0.0) for s in seeds), default=0.0)
        escalated = False
        if self.settings.graphrag.escalation_gate and detect_escalation(
            seeds, self._gate_threshold()
        ):
            escalated = True
            emit("query.escalated", question=question, top_score=seed_top)

        # R02-H11: proposition hits are primary evidence AND extra PPR seeds
        fact_lines: list[str] = []
        hits: list[dict] = []
        seed_ids = [s["id"] for s in seeds]
        if self.settings.graphrag.propositions_enabled:
            from knowledge_graph_foundry.graph.propositions import proposition_query

            try:
                hits = proposition_query(
                    self.driver,
                    embedded[0].embedding,
                    self.settings.graphrag.proposition_index_name,
                    top_k=self.settings.graphrag.proposition_top_k,
                )
            except Exception as exc:  # index absent until first optimize
                logger.debug(f"proposition retrieval unavailable: {exc}")
                hits = []
            fact_lines = [h["text"] for h in hits]
            if self.settings.graphrag.proposition_seeding:  # R03-H14
                for h in hits:
                    for eid in h["entity_ids"]:
                        if eid not in seed_ids:
                            seed_ids.append(eid)

        nodes = seeds
        if self.settings.graphrag.ppr_enabled:
            ranked = ppr_query(
                self.driver,
                seed_ids,
                top_n=self.settings.graphrag.ppr_top_n,
                damping=self.settings.graphrag.ppr_damping,
            )
            if ranked:
                # union seeds and PPR-ranked nodes, seeds first, dedup by id
                seen = set()
                nodes = []
                for n in seeds + ranked:
                    if n["id"] not in seen:
                        seen.add(n["id"])
                        nodes.append(n)

        # R37-H382 rung 1 (H367-B): under escalation the proposition-seeded
        # entities join the rendered node set, scored by their proposition hit
        # so the render budget ranks them honestly
        if escalated and hits:
            have = {n["id"] for n in nodes}
            prop_score: dict[str, float] = {}
            for h in hits:
                for eid in h["entity_ids"]:
                    prop_score[eid] = max(prop_score.get(eid, 0.0), h.get("score", 0.0))
            extra = fetch_entities(self.driver, [e for e in prop_score if e not in have])
            for row in extra:
                row["score"] = prop_score[row["id"]]
            nodes = nodes + extra

        # R19-H205 (optional, default off): drop foreign-device render sections,
        # keeping the queried product (top seed) and every non-device node
        if self.settings.graphrag.foreign_device_exclusion and seeds:
            nodes = exclude_foreign_devices(nodes, {seeds[0]["id"]})

        # R03-H17 coverage signals: best vector/proposition hit score; the gate
        # signal (pure top-seed, R37-H382) rides beside the composite
        coverage = {
            "top_score": max(
                [s.get("score", 0.0) for s in seeds] + [h.get("score", 0.0) for h in hits] or [0.0]
            ),
            "seed_top_score": seed_top,
            "escalated": escalated,
        }

        cap = self.settings.graphrag.fanout_cap
        # R19-H211: index property values equal to a rendered node's name so the
        # carrier entity gets surfaced under that node (the prop-val linkage rule)
        prop_links: dict[str, list[str]] = {}

        scored_blocks: list[tuple[str, float]] = []
        supporting: list[str] = []
        with self.driver.session() as session:
            if self.settings.graphrag.prop_val_linkage and nodes:
                wanted = {
                    re.sub(r"\s+", " ", n["name"].casefold()).strip()
                    for n in nodes
                    if n.get("name")
                }
                wanted = {w for w in wanted if len(w) >= 4}
                if wanted:
                    val_rows = session.run(
                        "MATCH (c:Entity) "
                        "UNWIND [k IN keys(c) WHERE k STARTS WITH 'prop_'] AS k "
                        "WITH c, toLower(trim(toString(c[k]))) AS val "
                        "WHERE val IN $wanted "
                        "RETURN val, collect(DISTINCT c.name)[..3] AS carriers",
                        wanted=list(wanted),
                    ).data()
                    value_index: dict[str, list[str]] = {}
                    for r in val_rows:
                        key = re.sub(r"\s+", " ", (r["val"] or "").casefold()).strip()
                        value_index.setdefault(key, []).extend(r["carriers"])
                    for node in nodes:
                        carriers = [
                            c
                            for c in link_prop_values(node["name"], value_index)
                            if c != node["name"]
                        ]
                        if carriers:
                            prop_links[node["id"]] = carriers
            for node in nodes:
                if cap > 0:
                    # R19-H180: fetch the neighborhood then keep the top-`cap`
                    # neighbors ranked by embedding similarity to the query
                    rows = cap_fanout(
                        session.run(
                            "MATCH (e:Entity {id: $id})-[r]-(n:Entity) "
                            "WHERE r.valid_to IS NULL AND type(r) <> 'SIMILAR_TO' "
                            "RETURN type(r) AS rel, n.name AS name, n.embedding AS emb "
                            "LIMIT 100",
                            id=node["id"],
                        ).data(),
                        qv,
                        cap,
                    )
                else:
                    rows = session.run(
                        "MATCH (e:Entity {id: $id})-[r]-(n:Entity) "
                        "WHERE r.valid_to IS NULL AND type(r) <> 'SIMILAR_TO' "
                        "RETURN type(r) AS rel, n.name AS name LIMIT 15",
                        id=node["id"],
                    ).data()
                props = session.run(
                    "MATCH (e:Entity {id: $id}) RETURN properties(e) AS props",
                    id=node["id"],
                ).single()["props"]
                spec = {
                    k.removeprefix("prop_"): v for k, v in props.items() if k.startswith("prop_")
                }
                # R04-H21: the alias cluster is one identity - surface facts
                # recorded under any SAME_AS name for the retrieved name
                aliases = session.run(
                    "MATCH (e:Entity {id: $id})-[:SAME_AS*1..2]-(a:Entity) "
                    "WHERE a.id <> $id RETURN DISTINCT a.name AS name, properties(a) AS props "
                    "LIMIT 5",
                    id=node["id"],
                ).data()
                alias_names = [a["name"] for a in aliases]
                for a in aliases:
                    for k, v in a["props"].items():
                        if k.startswith("prop_"):
                            spec.setdefault(k.removeprefix("prop_"), v)
                supporting.append(node["name"])
                links = prop_links.get(node["id"], [])
                block = (
                    f"## {node['name']} ({', '.join(node.get('types', []))})\n"
                    + (f"Also known as: {', '.join(alias_names)}\n" if alias_names else "")
                    + (f"Referenced by: {', '.join(links)}\n" if links else "")
                    + f"{node.get('description', '')}\n"
                    f"Properties: {json.dumps(spec, default=str)}\n"
                    "Relations: " + "; ".join(f"{r['rel']} -> {r['name']}" for r in rows)
                )
                scored_blocks.append((block, node.get("score", 0.0)))

        # R19-H182: keep the top-similarity fraction of render mass (query-
        # similarity ranked, ~40% token cut at zero recall loss on the census)
        entity_blocks = truncate_to_budget(
            [(b, sc, float(len(b))) for b, sc in scored_blocks],
            self.settings.graphrag.render_budget,
        )

        # R03-H16: lost-in-the-middle mitigation - blocks arrive relevance-
        # ordered; interleave so the strongest sit at the head AND the tail
        if self.settings.graphrag.context_head_tail and len(entity_blocks) > 3:
            entity_blocks = entity_blocks[0::2] + entity_blocks[1::2][::-1]

        context_lines: list[str] = []
        if fact_lines:
            context_lines.append("## Facts\n" + "\n".join(f"- {t}" for t in fact_lines))
        context_lines.extend(entity_blocks)

        # R37-H382 rung 2 (H366): under escalation append the top query-anchored
        # span from the passage channel; a space mismatch refuses the span query
        # (never mixes spaces silently) but leaves the rung-0/1 render standing
        if escalated and self.settings.graphrag.passages_enabled:
            from knowledge_graph_foundry.extraction.embeddings import embed_channel_texts
            from knowledge_graph_foundry.graph.passages import check_space, passage_query

            ch = self.settings.embedding_channels.passages
            index = self.settings.graphrag.passage_index_name
            try:
                check_space(self.driver, index, ch.provider, ch.model)
                q_emb = embed_channel_texts([question], ch)[0]
                for h in passage_query(
                    self.driver, q_emb, index, self.settings.graphrag.passage_top_k
                ):
                    context_lines.append("## Source excerpt\n" + h["text"])
            except Exception as exc:
                logger.warning(f"passage escalation unavailable: {exc}")

        return context_lines, supporting, coverage

    def current_relationships(self, entity_id: str) -> list[dict]:
        """Currently-valid outgoing edges of an entity (R1 time-aware read)."""
        from knowledge_graph_foundry.graph.temporal import current_relationships

        return current_relationships(self.driver, entity_id)

    def relationship_history(self, entity_id: str, rel_type: str) -> list[dict]:
        """Full ordered history of one relationship type (R1 evolution record)."""
        from knowledge_graph_foundry.graph.temporal import relationship_history

        return relationship_history(self.driver, entity_id, rel_type)

    def search(self, embedding_or_text: "str | list[float]", top_k: int = 8) -> list[dict]:
        """Vector search over entities; accepts a text query or a raw embedding."""
        from knowledge_graph_foundry.extraction import generate_embeddings
        from knowledge_graph_foundry.graph.graphrag import vector_query

        if isinstance(embedding_or_text, str):
            probe = Entity.create(
                embedding_or_text[:80], types=["Query"], description=embedding_or_text
            )
            embedding = generate_embeddings([probe], self.settings.embeddings)[0].embedding
        else:
            embedding = embedding_or_text
        return vector_query(
            self.driver, embedding, self.settings.graphrag.vector_index_name, top_k=top_k
        )

    def wipe(self) -> None:
        """Delete all graph content and the control metanode."""
        with self.driver.session() as session:
            session.run("MATCH (n) DETACH DELETE n")


def build(
    purpose: str,
    source: "str | Path | None" = None,
    *,
    settings: Optional[Settings] = None,
    config_path: Optional[Path] = None,
    seed: Optional[str] = None,
    optimize: bool = False,
) -> Foundry:
    """Simplest form: build (or extend) a graph in one call and return a live
    Foundry to query.

        graph = build("compare CPAP machines", "data/manuals/")
        print(graph.query("AirSense 11 vs DreamStation pressure range?"))

    Initializes the project when the graph is empty (idempotent - safe to call
    again to ingest more), ingests ``source`` when given, and optionally runs
    GraphRAG optimization. Configure anything by passing ``settings`` (full
    control) or ``config_path`` (a config.yml); omit both for env/defaults.
    """
    foundry = Foundry(settings) if settings is not None else Foundry.from_config(config_path)
    if foundry.status().get("fsm_state", "EMPTY") == "EMPTY":
        foundry.init_project(purpose, seed)
    if source is not None:
        foundry.ingest(source)
    if optimize:
        foundry.optimize()
    return foundry
