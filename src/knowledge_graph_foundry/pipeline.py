"""Foundry pipeline - wires ingest -> extract -> resolve -> load per
lifecycle phase. The graph metanode is the single source of truth: every
public operation restores state from it first and persists back after.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from loguru import logger

from knowledge_graph_foundry.drift import DriftDetector
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
)
from knowledge_graph_foundry.models import Entity, Ontology, Relationship
from knowledge_graph_foundry.ontology.buffer import FluidBuffer
from knowledge_graph_foundry.ontology.clustering import apply_type_remap, cluster_types
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
        calibrator = (
            PosteriorCalibrator.from_json(state["calibration"])
            if state.get("calibration")
            else None
        )

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
        state_drift = None

        for file_path in files:
            emit("document.started", path=str(file_path))
            try:
                entities, relationships = self._extract_file(file_path, purpose, ontology)
            except Exception as exc:  # corrupt file: skip, continue run
                emit("document.skipped", path=str(file_path), reason=str(exc))
                logger.warning(f"skipping {file_path}: {exc}")
                continue

            if not entities:
                emit("document.skipped", path=str(file_path), reason="no entities")
                continue

            entities = self._embed(entities)
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
                    "drift_verdict": state_drift if lifecycle.state == "STABLE" else None,
                }
            )
            emit("document.completed", path=str(file_path), entities=len(entities))

        emit("load.completed", **summary)
        return summary

    # -- internals --------------------------------------------------------

    def _extract_file(
        self, file_path: Path, purpose: str, ontology: Ontology
    ) -> tuple[list[Entity], list[Relationship]]:
        from knowledge_graph_foundry.extraction import (
            apply_mapping,
            extract_document,
            structured_mapping,
        )

        if is_structured(file_path):
            rows = read_structured(file_path)
            if not rows:
                return [], []
            mapping = structured_mapping(rows[:5], purpose, self.engine)
            result = apply_mapping(rows, mapping, document_id=f"d_{file_path.stem}")
        else:
            document = read_document(file_path)
            chunks = chunk_document(
                document,
                chunk_size=self.settings.extraction.chunk_size,
                chunk_overlap=self.settings.extraction.chunk_overlap,
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
        return result.entities, result.relationships

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

        ontology, type_remap = cluster_types(
            buffer.ontology, purpose, self.engine, embed_fn=self._embed_texts
        )
        entities = [
            e.model_copy(update={"types": apply_type_remap(e.types, type_remap)})
            for e in buffer.entities
        ]
        result = resolve_entities(
            entities, self.settings.resolution, calibrator, engine=self.engine
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
            entities, self.settings.resolution, calibrator, engine=self.engine
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
        card = scorecard(self.driver)
        result = {"communities": communities, "summaries": summaries, "scorecard": card}
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

        context_lines, supporting = self._retrieve_local(question)
        result = self.engine.complete(
            [
                {
                    "role": "system",
                    "content": "Answer strictly from the provided knowledge graph context. "
                    "Name the entities supporting the answer. Say so when the graph lacks the answer.",
                },
                {
                    "role": "user",
                    "content": f"Question: {question}\n\nGraph context:\n\n"
                    + "\n\n".join(context_lines),
                },
            ],
            Answer,
        )
        return {
            "answer": result.answer,
            "supporting_entities": result.supporting_entities or supporting,
            "path": "ppr" if self.settings.graphrag.ppr_enabled else "vector",
        }

    def _retrieve_local(self, question: str) -> tuple[list[str], list[str]]:
        """Local retrieval: vector top-k seeds, expanded by PPR when enabled,
        each node rendered with its properties and currently-valid relations."""
        from knowledge_graph_foundry.extraction import generate_embeddings
        from knowledge_graph_foundry.graph.graphrag import ppr_query, vector_query

        probe = Entity.create(question[:80], types=["Query"], description=question)
        embedded = generate_embeddings([probe], self.settings.embeddings)
        seeds = vector_query(
            self.driver,
            embedded[0].embedding,
            self.settings.graphrag.vector_index_name,
            top_k=self.settings.graphrag.top_k,
        )
        nodes = seeds
        if self.settings.graphrag.ppr_enabled:
            ranked = ppr_query(
                self.driver,
                [s["id"] for s in seeds],
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

        context_lines: list[str] = []
        supporting: list[str] = []
        with self.driver.session() as session:
            for node in nodes:
                rows = session.run(
                    "MATCH (e:Entity {id: $id})-[r]-(n:Entity) "
                    "WHERE r.valid_to IS NULL "
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
                supporting.append(node["name"])
                context_lines.append(
                    f"## {node['name']} ({', '.join(node.get('types', []))})\n"
                    f"{node.get('description', '')}\n"
                    f"Properties: {json.dumps(spec, default=str)}\n"
                    "Relations: " + "; ".join(f"{r['rel']} -> {r['name']}" for r in rows)
                )
        return context_lines, supporting

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
