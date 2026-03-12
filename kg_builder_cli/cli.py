"""CLI entry points for Knowledge Graph Foundry."""

from __future__ import annotations

from pathlib import Path

import typer

from kg_builder_cli.config import APP_NAME, APP_SHORT, config_dir, logger, ontology_file

app = typer.Typer(name=APP_SHORT, help=f"{APP_NAME} CLI", invoke_without_command=True)


@app.callback(invoke_without_command=True)
def main_callback(ctx: typer.Context):
    """Launch TUI when no subcommand is given."""
    if ctx.invoked_subcommand is None:
        from kg_builder_cli.tui.app import KGBuilderApp

        tui_app = KGBuilderApp()
        tui_app.run()


@app.command()
def ingest(
    source: Path = typer.Argument(..., help="Path to file or directory to ingest"),
    batch: bool = typer.Option(
        False, "--batch", help="Run in autonomous mode without interactive checkpoints"
    ),
    ontology: Path | None = typer.Option(None, "--ontology", help="Path to ontology seed file"),
    config_path: Path | None = typer.Option(None, "--config", help="Path to config.yml"),
    chunk_size: int | None = typer.Option(None, "--chunk-size", help="Override chunk size"),
    chunk_overlap: int | None = typer.Option(
        None, "--chunk-overlap", help="Override chunk overlap"
    ),
    concurrency: int | None = typer.Option(None, "--concurrency", help="Override concurrency"),
    fluid: bool | None = typer.Option(
        None, "--fluid/--no-fluid", help="Enable/disable fluid schema curing"
    ),
    cure: bool = typer.Option(False, "--cure", help="Force-cure after first document"),
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Enable verbose event logging with full payloads"
    ),
    event_log: Path | None = typer.Option(
        None, "--event-log", help="Write JSONL event log to file path"
    ),
    processing_log: Path | None = typer.Option(
        None, "--processing-log", help="Write execution log to file path (default: stdout)"
    ),
):
    """Ingest documents into the knowledge graph."""
    from kg_builder_cli.events import (
        clear_event_log,
        get_event_log_count,
        register_default_handlers,
        register_event_accumulator,
        register_verbose_handlers,
    )
    from kg_builder_cli.ontology.buffer import OntologyBuffer
    from kg_builder_cli.settings import load_config

    # Redirect loguru to file when --processing-log is provided
    if processing_log is not None:
        processing_log.parent.mkdir(parents=True, exist_ok=True)
        logger.remove()
        logger.add(str(processing_log), colorize=False)

    # Set up event bus (accumulator registered conditionally below)
    clear_event_log()
    register_default_handlers()
    if verbose:
        register_verbose_handlers()

    logger.info("ingesting from {}", source)

    # Build CLI overrides
    overrides = {}
    if chunk_size is not None:
        overrides.setdefault("extract", {})["chunk_size"] = chunk_size
    if chunk_overlap is not None:
        overrides.setdefault("extract", {})["chunk_overlap"] = chunk_overlap
    if concurrency is not None:
        overrides.setdefault("extract", {})["concurrency"] = concurrency

    config = load_config(config_path=config_path, overrides=overrides if overrides else None)

    # Enable streaming event log when --event-log path is provided or config enables it
    if event_log is not None:
        register_event_accumulator(event_log)
        logger.info("event log streaming to {}", event_log)
    elif config.extract.event_log:
        event_log = config_dir() / "events.log"
        register_event_accumulator(event_log)
        logger.info("event log streaming to {}", event_log)

    # Resolve fluid mode: CLI flag > config > default
    curing_enabled = fluid if fluid is not None else config.curing.enabled
    # Fluid mode only applies when no ontology seed is provided
    if curing_enabled and ontology:
        logger.warning("--fluid ignored: ontology seed provided, using seeded workflow")
        curing_enabled = False

    logger.info(
        "config loaded: model={}, neo4j={}, fluid={}",
        config.llm.model,
        config.neo4j.uri,
        curing_enabled,
    )

    # Initialize ontology buffer
    buffer = None
    if ontology and ontology.suffix in (".yml", ".yaml"):
        buffer = OntologyBuffer.from_yaml(ontology, config.ontology_buffer)
        logger.info("ontology buffer loaded from {}", ontology)
    elif ontology is None:
        buffer = OntologyBuffer(config.ontology_buffer)

    # Collect files to process
    if source.is_dir():
        files = sorted(
            p
            for p in source.iterdir()
            if p.suffix.lower() in (".pdf", ".txt", ".md", ".docx", ".json", ".jsonl")
        )
    else:
        files = [source]

    if not files:
        logger.error("no supported files found in {}", source)
        raise typer.Exit(1)

    logger.info("found {} file(s) to ingest", len(files))

    from kg_builder_cli.events import signals
    from kg_builder_cli.events import types as etypes
    from kg_builder_cli.extraction.extract import LLMAuthError
    from kg_builder_cli.extraction.unstructured import ExtractionFailedError

    signals.ingestion_started.send(
        signals.ingestion_started,
        event=etypes.IngestionStarted(
            files=[str(f) for f in files],
            mode="fluid" if curing_enabled else "direct",
            model=config.llm.model,
        ),
    )

    try:
        if curing_enabled:
            _ingest_fluid(files, config, buffer, cure)
        else:
            _ingest_direct(files, config, buffer)
    except LLMAuthError as exc:
        logger.error("LLM authentication failed - aborting ingestion")
        logger.error("{}", exc)
        raise typer.Exit(1) from None
    except ExtractionFailedError as exc:
        logger.error("extraction failed: {}", exc)
        raise typer.Exit(1) from None

    # Flush ontology buffer after all files
    if buffer and config.ontology_buffer.flush_on_complete:
        buffer._maybe_evolve()  # final evolution pass before flush
        flush_path = ontology_file()
        buffer.flush(flush_path)
        logger.info("ontology buffer flushed: coverage={:.0%}", buffer.coverage())

    signals.ingestion_completed.send(
        signals.ingestion_completed,
        event=etypes.IngestionCompleted(
            total_docs=len(files),
            total_entities=0,
            total_rels=0,
        ),
    )

    if event_log is not None:
        logger.info("event log: {} events written to {}", get_event_log_count(), event_log)

    logger.info("ingestion complete")


def _ingest_direct(
    files: list[Path],
    config,
    buffer,
) -> None:
    """Standard per-document ingestion with immediate Neo4j loading."""
    from kg_builder_cli.extraction.unstructured import ingest_document
    from kg_builder_cli.loading.loader import load_extraction

    for file_path in files:
        logger.info("processing: {}", file_path.name)
        result = ingest_document(file_path, config, buffer=buffer)
        logger.info(
            "extracted {} entities, {} relationships, {} facts",
            len(result.entities),
            len(result.relationships),
            len(result.facts),
        )

        load_result = load_extraction(result, config)
        logger.info(
            "loaded: {} created, {} merged, {} relationships",
            load_result.nodes_created,
            load_result.nodes_merged,
            load_result.relationships_created,
        )

        if buffer:
            buffer._maybe_evolve()


def _ingest_fluid(
    files: list[Path],
    config,
    buffer,
    force_cure: bool = False,
) -> None:
    """Two-phase ingestion: fluid accumulation then cured direct loading.

    Phase 1 (fluid): Extract and accumulate in memory, evolve schema.
    Curing event: Consolidate all accumulated results and flush to Neo4j.
    Phase 2 (cured): Remaining files load directly per-document.
    """
    from kg_builder_cli.curing.accumulator import FluidAccumulator
    from kg_builder_cli.curing.detector import CuringDetector
    from kg_builder_cli.curing.metrics import StabilityMetrics
    from kg_builder_cli.extraction.unstructured import ingest_document
    from kg_builder_cli.loading.loader import (
        load_doc_chunks,
        load_extraction,
        resolve_against_graph,
    )

    accumulator = FluidAccumulator(deferred_dedup=config.extract.deferred_dedup)
    detector = CuringDetector(config.curing)
    metrics_tracker = StabilityMetrics(
        variance_window=config.curing.metrics_variance_window,
    )

    cured = False
    exemplar_index = None  # built at curing time for Bayesian resolution

    for i, file_path in enumerate(files):
        if cured:
            # Phase 2: direct load with graph-aware resolution
            logger.info("[cured] processing: {}", file_path.name)
            result = ingest_document(
                file_path,
                config,
                buffer=buffer,
                exemplar_index=exemplar_index,
            )
            logger.info(
                "[cured] extracted {} entities, {} relationships",
                len(result.entities),
                len(result.relationships),
            )

            # Post-cure metric tracking
            if buffer:
                stability = metrics_tracker.record(buffer.frequencies())
                if stability:
                    import math

                    jsd = stability.get("js_divergence", float("nan"))
                    chao1 = stability.get("chao1_coverage", float("nan"))
                    ent_d = stability.get("entropy_shannon_delta", float("nan"))
                    jsd_s = f"{jsd:.4f}" if not math.isnan(jsd) else "n/a"
                    chao1_s = f"{chao1:.3f}" if not math.isnan(chao1) else "n/a"
                    ent_d_s = f"{ent_d:.4f}" if not math.isnan(ent_d) else "n/a"
                    logger.info(
                        "[cured] stability: jsd={}, chao1_cov={}, entropy_delta={}",
                        jsd_s,
                        chao1_s,
                        ent_d_s,
                    )

            # Drift detection
            remap_rate = result.metadata.remap_count / max(len(result.entities), 1)
            if detector.check_drift(remap_rate):
                should_recure = False
                if config.curing.generative_curing:
                    from kg_builder_cli.curing.generative import llm_should_recure

                    cured_types = list(buffer.type_names()) if buffer else []
                    decision = llm_should_recure(
                        cured_ontology_types=cured_types,
                        remap_history=detector._remap_history,
                        recent_remap_rate=remap_rate,
                        remap_count=result.metadata.remap_count,
                        intent=config.ontology_buffer.resolution_intent,
                        stability=stability or {},
                        llm_config=config.llm,
                        neo4j_config=config.neo4j,
                    )
                    if decision is not None:
                        should_recure = decision.should_recure
                        if should_recure:
                            logger.info("[cured] LLM advises re-cure: {}", decision.reasoning)
                        else:
                            logger.info("[cured] LLM dismisses drift: {}", decision.reasoning)
                    else:
                        logger.warning(
                            "[cured] generative re-cure failed, falling back to re_cure_on_drift={}",
                            config.curing.re_cure_on_drift,
                        )
                        should_recure = config.curing.re_cure_on_drift
                else:
                    should_recure = config.curing.re_cure_on_drift

                if should_recure:
                    logger.warning(
                        "[cured] DRIFT detected: re-entering fluid phase (remap rate {:.0%} for {} consecutive docs)",
                        remap_rate,
                        config.curing.drift_window,
                    )
                    cured = False
                    accumulator = FluidAccumulator(deferred_dedup=config.extract.deferred_dedup)
                    detector = CuringDetector(config.curing)
                    metrics_tracker = StabilityMetrics(
                        variance_window=config.curing.metrics_variance_window,
                    )
                    # Re-process this document in fluid mode on next iteration
                    # (it's already extracted, so just add to accumulator)
                    accumulator.add_result(result)
                    if buffer:
                        buffer.accumulate_from_result(result.entities, result.relationships)
                    continue
                else:
                    logger.warning(
                        "[cured] DRIFT: {:.0%} entities remapped for {} consecutive docs",
                        remap_rate,
                        config.curing.drift_window,
                    )

            # Graph-aware resolution: remap to existing graph types
            result = resolve_against_graph(result, config)

            load_result = load_extraction(result, config)
            logger.info(
                "[cured] loaded: {} created, {} merged, {} relationships",
                load_result.nodes_created,
                load_result.nodes_merged,
                load_result.relationships_created,
            )

            if buffer:
                buffer._maybe_evolve()
            continue

        # Phase 1: fluid accumulation
        logger.info("[fluid] processing: {}", file_path.name)

        # Capture types before extraction for new type detection
        types_before = buffer.type_names() if buffer else set()

        result = ingest_document(file_path, config, buffer=buffer)
        accumulator.add_result(result)
        logger.info(
            "[fluid] extracted {} entities, {} relationships (accumulated: {} docs)",
            len(result.entities),
            len(result.relationships),
            accumulator.doc_count,
        )

        # buffer.accumulate_from_result() already called inside ingest_document
        types_after = buffer.type_names() if buffer else set()
        new_types = types_after - types_before

        # Compute stability metrics and record curing state
        coverage = buffer.coverage() if buffer else 0.0
        stability = metrics_tracker.record(buffer.frequencies()) if buffer else {}
        detector.record(coverage, new_types, stability)
        logger.info("[fluid] curing status: {}", detector.status())

        # Log key stability metrics
        if stability:
            import math

            jsd = stability.get("js_divergence", float("nan"))
            chao1 = stability.get("chao1_coverage", float("nan"))
            heaps = stability.get("heaps_beta", float("nan"))
            ent_d = stability.get("entropy_shannon_delta", float("nan"))
            jsd_s = f"{jsd:.4f}" if not math.isnan(jsd) else "n/a"
            chao1_s = f"{chao1:.3f}" if not math.isnan(chao1) else "n/a"
            heaps_s = f"{heaps:.3f}" if not math.isnan(heaps) else "n/a"
            ent_d_s = f"{ent_d:.4f}" if not math.isnan(ent_d) else "n/a"
            logger.info(
                "[fluid] stability: jsd={}, chao1_cov={}, heaps_beta={}, entropy_delta={}",
                jsd_s,
                chao1_s,
                heaps_s,
                ent_d_s,
            )

        # Evolve hierarchy/guide after each document
        if buffer:
            buffer._maybe_evolve()

        # Check curing conditions
        should_cure = False
        if force_cure:
            logger.warning("[fluid] force-cure requested after first document")
            should_cure = True
        elif (
            config.curing.generative_curing
            and detector.docs_processed >= config.curing.min_documents
        ):
            from kg_builder_cli.curing.generative import llm_should_cure

            decision = llm_should_cure(
                type_names=buffer.type_names() if buffer else set(),
                frequencies=buffer.frequencies() if buffer else {},
                coverage=coverage,
                intent=config.ontology_buffer.resolution_intent,
                stability=stability or {},
                metrics_history=detector._metrics_history,
                new_types_history=detector._new_types_history,
                docs_processed=detector.docs_processed,
                total_entities=len(accumulator.all_entities()),
                llm_config=config.llm,
                min_documents=config.curing.min_documents,
                accumulator=accumulator,
                buffer=buffer,
                max_tool_calls=config.curing.generative_max_tool_calls,
            )
            if decision is not None:
                detector.record_llm_vote(decision.should_cure)
                if decision.should_cure:
                    logger.info("[fluid] LLM advises cure: {}", decision.reasoning)
                    should_cure = True
                else:
                    logger.info("[fluid] LLM advises continue: {}", decision.reasoning)
            else:
                logger.warning("[fluid] generative curing failed, falling back to metrics")
                should_cure = _check_metric_curing(detector)

        # Early stopping: patience-based auto-cure
        if (
            not should_cure
            and config.curing.generative_curing
            and detector.patience_exceeded(config.curing.generative_patience)
        ):
            threshold = max(
                3, int(config.curing.max_fluid_documents * config.curing.generative_patience)
            )
            logger.info(
                "[fluid] EARLY STOP: {} consecutive cure votes (patience {:.0%} of {} docs)",
                threshold,
                config.curing.generative_patience,
                config.curing.max_fluid_documents,
            )
            should_cure = True

        if not should_cure and not force_cure and not config.curing.generative_curing:
            should_cure = _check_metric_curing(detector)

        # Safety net ALWAYS applies
        if not should_cure and detector.is_force_required():
            logger.warning(
                "[fluid] SAFETY NET: force-curing at max_fluid_documents={} (signal-based curing did not trigger)",
                config.curing.max_fluid_documents,
            )
            should_cure = True

        if should_cure:
            # Curing event: type clustering + consolidation + flush
            import asyncio

            from kg_builder_cli.curing.type_clustering import (
                apply_type_mapping,
                cluster_types,
            )
            from kg_builder_cli.extraction.dedup import normalize_entity_ids

            cured_ontology = (
                buffer.snapshot(
                    resolution_intent=config.ontology_buffer.resolution_intent or "",
                )
                if buffer
                else None
            )
            logger.info(
                "[curing] consolidating {} documents, ontology has {} types",
                accumulator.doc_count,
                len(cured_ontology.entity_types) if cured_ontology else 0,
            )

            # LLM-assisted type clustering
            freqs = buffer.frequencies() if buffer else {}
            entity_type_names = list(buffer.type_names()) if buffer else []
            if entity_type_names:
                type_mapping = asyncio.run(
                    cluster_types(
                        discovered_types=entity_type_names,
                        frequencies=freqs,
                        intent=config.ontology_buffer.resolution_intent,
                        model=config.llm.model,
                        provider=config.llm.provider,
                        region=config.llm.region,
                        profile=config.llm.profile,
                    )
                )

                # Validate merges before applying
                all_entities = accumulator.all_entities()
                from kg_builder_cli.curing.merge_validation import validate_type_clustering

                validation = validate_type_clustering(
                    type_mapping,
                    freqs,
                    all_entities,
                    threshold=config.curing.merge_confidence_threshold,
                )
                type_mapping = validation.approved_mapping

                # Apply type mapping to accumulated entities
                apply_type_mapping(all_entities, type_mapping)

                # Re-normalize IDs after type remapping
                all_rels = accumulator.all_relationships()
                normalize_entity_ids(all_entities, all_rels)

            # Load per-document Document + Chunk nodes before consolidation
            for individual_result in accumulator._results:
                load_doc_chunks(individual_result, config)
                logger.debug(
                    "[curing] loaded doc+chunks for '{}'",
                    individual_result.metadata.source,
                )

            merged_result = accumulator.consolidate(
                cured_ontology,
                config.extract,
                type_frequencies=freqs,
                skip_type_enforcement=True,
                llm_config=config.llm,
                neo4j_config=config.neo4j,
            )
            logger.info(
                "[curing] merged result: {} entities, {} relationships",
                len(merged_result.entities),
                len(merged_result.relationships),
            )

            # Load consolidated entities + relationships only (skip doc/chunks)
            load_result = load_extraction(merged_result, config, skip_doc_chunks=True)
            logger.info(
                "[curing] loaded: {} created, {} merged, {} relationships",
                load_result.nodes_created,
                load_result.nodes_merged,
                load_result.relationships_created,
            )

            # Build exemplar index for Bayesian resolution in cured phase
            if config.extract.bayesian_resolution and buffer:
                exemplar_index = _build_exemplar_index(buffer, config)

            cured = True

    # If never cured (all files processed in fluid phase), flush anyway
    if not cured and accumulator.doc_count > 0:
        import asyncio

        from kg_builder_cli.curing.type_clustering import (
            apply_type_mapping,
            cluster_types,
        )
        from kg_builder_cli.extraction.dedup import normalize_entity_ids

        logger.warning(
            "[fluid] ingestion complete without curing ({} docs), flushing accumulated results",
            accumulator.doc_count,
        )

        # LLM-assisted type clustering before flush
        freqs = buffer.frequencies() if buffer else {}
        entity_type_names = list(buffer.type_names()) if buffer else []
        if entity_type_names:
            type_mapping = asyncio.run(
                cluster_types(
                    discovered_types=entity_type_names,
                    frequencies=freqs,
                    intent=config.ontology_buffer.resolution_intent,
                    model=config.llm.model,
                    provider=config.llm.provider,
                    region=config.llm.region,
                    profile=config.llm.profile,
                )
            )
            # Validate merges before applying
            all_entities = accumulator.all_entities()
            from kg_builder_cli.curing.merge_validation import validate_type_clustering

            validation = validate_type_clustering(
                type_mapping,
                freqs,
                all_entities,
                threshold=config.curing.merge_confidence_threshold,
            )
            type_mapping = validation.approved_mapping

            apply_type_mapping(all_entities, type_mapping)
            all_rels = accumulator.all_relationships()
            normalize_entity_ids(all_entities, all_rels)

        # Load per-document Document + Chunk nodes before consolidation
        for individual_result in accumulator._results:
            load_doc_chunks(individual_result, config)
            logger.debug(
                "[flush] loaded doc+chunks for '{}'",
                individual_result.metadata.source,
            )

        cured_ontology = (
            buffer.snapshot(
                resolution_intent=config.ontology_buffer.resolution_intent or "",
            )
            if buffer
            else None
        )
        merged_result = accumulator.consolidate(
            cured_ontology,
            config.extract,
            type_frequencies=freqs,
            skip_type_enforcement=True,
            llm_config=config.llm,
            neo4j_config=config.neo4j,
        )
        # Load consolidated entities + relationships only (skip doc/chunks)
        load_result = load_extraction(merged_result, config, skip_doc_chunks=True)
        logger.info(
            "[flush] loaded: {} created, {} merged, {} relationships",
            load_result.nodes_created,
            load_result.nodes_merged,
            load_result.relationships_created,
        )


def _check_metric_curing(detector) -> bool:
    """Check metric-based curing conditions: converged, plateau, or heuristic."""
    if detector.is_converged():
        logger.info("[fluid] schema converged (metric-based)")
        return True
    if detector.is_plateau():
        logger.info("[fluid] schema plateau detected (metric-based)")
        return True
    if detector.is_cured():
        logger.info("[fluid] schema has cured naturally (heuristic)")
        return True
    return False


def _build_exemplar_index(buffer, config):
    """Build FAISS exemplar index from buffer's frozen exemplars."""
    from kg_builder_cli.extraction.embeddings import generate_embeddings
    from kg_builder_cli.extraction.exemplar_index import ExemplarIndex
    from kg_builder_cli.types.extraction import Entity

    snapshot = buffer.snapshot(resolution_intent="")
    if not snapshot.type_exemplars:
        logger.info("[curing] no exemplars available, skipping FAISS index")
        return None

    # Generate embeddings for exemplar entities
    exemplar_entities = []
    for type_name, exemplars in snapshot.type_exemplars.items():
        for ex in exemplars:
            exemplar_entities.append(
                Entity(
                    id=f"exemplar_{ex.name.lower().replace(' ', '_')}",
                    name=ex.name,
                    type=type_name,
                    description=f"Exemplar for type {type_name}",
                )
            )

    if not exemplar_entities:
        return None

    logger.info("[curing] generating embeddings for {} exemplars", len(exemplar_entities))
    exemplar_entities = generate_embeddings(
        exemplar_entities,
        model=config.extract.embedding_model,
    )

    # Build embedding lookup
    embeddings: dict[str, list[float]] = {}
    for ent in exemplar_entities:
        if ent.embedding:
            embeddings[ent.name] = ent.embedding

    index = ExemplarIndex()
    index.build(snapshot.type_exemplars, embeddings)

    if index.is_built:
        logger.info("[curing] FAISS exemplar index built successfully")
        return index

    return None


@app.command()
def query(
    question: str = typer.Argument(..., help="Natural language question about the graph"),
):
    """Query the knowledge graph."""
    logger.info("query: {}", question)
    logger.warning("Query agent not yet implemented")


@app.command()
def init():
    """Initialize .kgf/ directory with default configuration."""
    from kg_builder_cli.settings.defaults import DEFAULTS

    kg_dir = config_dir()
    if kg_dir.exists():
        logger.info("{} already exists", kg_dir)
        return

    import yaml

    kg_dir.mkdir()
    (kg_dir / "schemas").mkdir()
    (kg_dir / "extractions").mkdir()
    (kg_dir / "memory").mkdir()
    (kg_dir / "migrations").mkdir()
    (kg_dir / "runs").mkdir()

    config_path = kg_dir / "config.yml"
    config_path.write_text(yaml.dump(DEFAULTS, default_flow_style=False, sort_keys=False))
    logger.info("created {} with default config", kg_dir)


def main():
    """Entry point."""
    app()


if __name__ == "__main__":
    main()
