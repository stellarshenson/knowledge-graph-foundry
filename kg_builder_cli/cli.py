"""CLI entry points for kg-builder-cli."""

from __future__ import annotations

from pathlib import Path

from loguru import logger
import typer

app = typer.Typer(name="kg", help="Knowledge Graph Builder CLI", invoke_without_command=True)


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
):
    """Ingest documents into the knowledge graph."""
    from kg_builder_cli.config import load_config
    from kg_builder_cli.ontology.buffer import OntologyBuffer

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

    if curing_enabled:
        _ingest_fluid(files, config, buffer, cure)
    else:
        _ingest_direct(files, config, buffer)

    # Flush ontology buffer after all files
    if buffer and config.ontology_buffer.flush_on_complete:
        flush_path = Path.cwd() / ".kg-builder" / "ontology.yml"
        buffer.flush(flush_path)
        logger.info("ontology buffer flushed: coverage={:.0%}", buffer.coverage())

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

    accumulator = FluidAccumulator()
    detector = CuringDetector(config.curing)
    metrics_tracker = StabilityMetrics(
        variance_window=config.curing.metrics_variance_window,
    )

    cured = False
    cure_index = len(files)  # default: all files in fluid phase
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

            # Graph-aware resolution: remap to existing graph types
            result = resolve_against_graph(result, config)

            load_result = load_extraction(result, config)
            logger.info(
                "[cured] loaded: {} created, {} merged, {} relationships",
                load_result.nodes_created,
                load_result.nodes_merged,
                load_result.relationships_created,
            )
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

        # Check curing conditions
        should_cure = False
        if force_cure:
            logger.warning("[fluid] force-cure requested after first document")
            should_cure = True
        elif detector.is_converged():
            logger.info("[fluid] schema converged (metric-based)")
            should_cure = True
        elif detector.is_cured():
            logger.info("[fluid] schema has cured naturally (heuristic)")
            should_cure = True
        elif len(accumulator.all_entities()) >= config.curing.max_fluid_entities:
            logger.warning(
                "[fluid] entity budget exceeded: {} >= max_fluid_entities={}",
                len(accumulator.all_entities()),
                config.curing.max_fluid_entities,
            )
            should_cure = True
        elif detector.is_force_required():
            logger.warning(
                "[fluid] force-curing at max_fluid_documents={}",
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

            # Prune low-frequency types before clustering
            if buffer:
                buffer.prune_low_frequency_types(config.curing.enforcement_threshold)

            cured_ontology = buffer.snapshot() if buffer else None
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
                        intent=config.ontology_buffer.intent,
                        model=config.llm.model,
                        provider=config.llm.provider,
                        region=config.llm.region,
                        profile=config.llm.profile,
                    )
                )

                # Apply type mapping to accumulated entities
                all_entities = accumulator.all_entities()
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
            cure_index = i + 1

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

        # Prune low-frequency types before clustering
        if buffer:
            buffer.prune_low_frequency_types(config.curing.enforcement_threshold)

        # LLM-assisted type clustering before flush
        freqs = buffer.frequencies() if buffer else {}
        entity_type_names = list(buffer.type_names()) if buffer else []
        if entity_type_names:
            type_mapping = asyncio.run(
                cluster_types(
                    discovered_types=entity_type_names,
                    frequencies=freqs,
                    intent=config.ontology_buffer.intent,
                    model=config.llm.model,
                    provider=config.llm.provider,
                    region=config.llm.region,
                    profile=config.llm.profile,
                )
            )
            all_entities = accumulator.all_entities()
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

        cured_ontology = buffer.snapshot() if buffer else None
        merged_result = accumulator.consolidate(
            cured_ontology,
            config.extract,
            type_frequencies=freqs,
        )
        # Load consolidated entities + relationships only (skip doc/chunks)
        load_result = load_extraction(merged_result, config, skip_doc_chunks=True)
        logger.info(
            "[flush] loaded: {} created, {} merged, {} relationships",
            load_result.nodes_created,
            load_result.nodes_merged,
            load_result.relationships_created,
        )


def _build_exemplar_index(buffer, config):
    """Build FAISS exemplar index from buffer's frozen exemplars."""
    from kg_builder_cli.extraction.embeddings import generate_embeddings
    from kg_builder_cli.extraction.exemplar_index import ExemplarIndex
    from kg_builder_cli.types.extraction import Entity

    snapshot = buffer.snapshot()
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
    """Initialize .kg-builder/ directory with default configuration."""
    from kg_builder_cli.config.defaults import DEFAULTS

    kg_dir = Path.cwd() / ".kg-builder"
    if kg_dir.exists():
        logger.info(".kg-builder/ already exists")
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
