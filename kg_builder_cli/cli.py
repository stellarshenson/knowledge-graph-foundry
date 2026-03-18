"""CLI entry points for Knowledge Graph Foundry."""

from __future__ import annotations

from pathlib import Path

import typer

from kg_builder_cli.config import (
    APP_NAME,
    APP_SHORT,
    STRUCTURED_EXTENSIONS,
    UNSTRUCTURED_EXTENSIONS,
    config_dir,
    logger,
    ontology_file,
)

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
    source: Path | None = typer.Argument(None, help="Path to file or directory to ingest"),
    inputs: list[Path] | None = typer.Option(
        None, "--input", "-i", help="Input file or directory (repeatable)"
    ),
    structured: bool = typer.Option(
        False, "--structured", help="Use structured pipeline (JSON/JSONL/CSV/XLSX)"
    ),
    unstructured: bool = typer.Option(
        False, "--unstructured", help="Use unstructured pipeline (PDF/TXT/MD/DOCX) [default]"
    ),
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

    # Merge sources: positional SOURCE and --input options
    all_sources: list[Path] = []
    if source is not None:
        all_sources.append(source)
    if inputs:
        all_sources.extend(inputs)
    if not all_sources:
        logger.error("no input specified - provide SOURCE argument or --input options")
        raise typer.Exit(1)

    # Resolve pipeline mode: --structured and --unstructured are mutually exclusive
    if structured and unstructured:
        logger.error("--structured and --unstructured are mutually exclusive")
        raise typer.Exit(1)
    pipeline_mode = "structured" if structured else "unstructured"

    logger.info("ingesting from {} source(s) [{}]", len(all_sources), pipeline_mode)

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
        "config loaded: model={}, neo4j={}, fluid={}, pipeline={}",
        config.llm.model,
        config.neo4j.uri,
        curing_enabled,
        pipeline_mode,
    )
    logger.info(
        "settings: chunk_size={}, overlap={}, concurrency={}, embeddings={}, bayesian={}",
        config.extract.chunk_size,
        config.extract.chunk_overlap,
        config.extract.concurrency,
        config.extract.use_embeddings,
        config.extract.bayesian_resolution,
    )
    if config.llm.rate_limit:
        logger.info(
            "rate limit: {:.1f} req/s",
            config.llm.rate_limit.requests_per_second,
        )

    # Initialize ontology buffer
    buffer = None
    if ontology and ontology.suffix in (".yml", ".yaml"):
        buffer = OntologyBuffer.from_yaml(ontology, config.ontology_buffer)
        logger.info("ontology buffer loaded from {}", ontology)
    elif ontology is None:
        buffer = OntologyBuffer(config.ontology_buffer)

    # Collect files from all sources, filtered by pipeline mode
    allowed_ext = STRUCTURED_EXTENSIONS if structured else UNSTRUCTURED_EXTENSIONS
    files: list[Path] = []
    for src in all_sources:
        if src.is_dir():
            files.extend(sorted(p for p in src.iterdir() if p.suffix.lower() in allowed_ext))
        elif src.is_file():
            files.append(src)
        else:
            logger.warning("source not found, skipping: {}", src)

    if not files:
        logger.error("no supported files found across {} source(s)", len(all_sources))
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

    # --- FSM initialization ---
    fsm_ctx = _init_fsm(config, curing_enabled, ontology is not None)
    if fsm_ctx:
        logger.info(
            "FSM initialized: state={}, graph_id={}, run_id={}",
            fsm_ctx.state,
            fsm_ctx.graph_id,
            fsm_ctx.run_id,
        )

    # --- Graph-authoritative buffer initialization (FSC-2) ---
    if fsm_ctx and fsm_ctx.ontology_hash is not None and buffer is not None:
        # Existing graph with known ontology hash - check seed dedup
        seed_hash = buffer.compute_hash()
        graph_hash = fsm_ctx.ontology_hash
        if seed_hash == graph_hash:
            logger.info("seed already consumed (hash={}), skipping", seed_hash)
            # Load buffer from graph instead of seed
            try:
                from neo4j import GraphDatabase as _GDB

                _drv = _GDB.driver(
                    config.neo4j.uri,
                    auth=(config.neo4j.user, config.neo4j.password),
                )
                try:
                    buffer = OntologyBuffer.from_graph(_drv, config.ontology_buffer)
                finally:
                    _drv.close()
            except Exception:
                logger.debug("from_graph() failed, keeping seed buffer")
        else:
            logger.info(
                "seed hash differs ({} vs {}), merging",
                seed_hash,
                graph_hash,
            )
    elif fsm_ctx and fsm_ctx.ontology_hash is not None and buffer is not None:
        pass  # seed provided, graph has hash - handled above
    elif fsm_ctx and fsm_ctx.ontology_hash is not None and ontology is None:
        # No seed provided, existing graph - reconstruct from graph
        try:
            from neo4j import GraphDatabase as _GDB

            _drv = _GDB.driver(
                config.neo4j.uri,
                auth=(config.neo4j.user, config.neo4j.password),
            )
            try:
                # Cache-first: check if ontology.yml exists and hash matches
                ont_path = ontology_file()
                if ont_path.exists():
                    cached_buffer = OntologyBuffer.from_yaml(ont_path, config.ontology_buffer)
                    cached_hash = cached_buffer.compute_hash()
                    if cached_hash == fsm_ctx.ontology_hash:
                        buffer = cached_buffer
                        logger.info(
                            "ontology buffer loaded from cache (hash verified): {} types",
                            len(buffer.type_names()),
                        )
                    else:
                        logger.warning(
                            "ontology cache hash mismatch ({} vs {}), rebuilding from graph",
                            cached_hash,
                            fsm_ctx.ontology_hash,
                        )
                        buffer = OntologyBuffer.from_graph(_drv, config.ontology_buffer)
                else:
                    buffer = OntologyBuffer.from_graph(_drv, config.ontology_buffer)
            finally:
                _drv.close()
        except Exception:
            logger.debug("graph buffer reconstruction failed, using empty buffer")
            if buffer is None:
                buffer = OntologyBuffer(config.ontology_buffer)

    try:
        if curing_enabled:
            _total_entities, _total_rels = _ingest_fluid(
                files,
                config,
                buffer,
                cure,
                fsm_ctx=fsm_ctx,
            )
        else:
            _total_entities, _total_rels = _ingest_direct(files, config, buffer, fsm_ctx=fsm_ctx)
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

    # --- FSM run completion ---
    if fsm_ctx:
        fsm_ctx.complete_run()
        _update_metanode_safe(config, fsm_ctx)
        # Safety net: clean up any orphaned fluid cache nodes
        _delete_fluid_cache_safe(config, fsm_ctx)
        logger.info(
            "FSM run completed: state={}, graph_id={}, run_count={}",
            fsm_ctx.state,
            fsm_ctx.graph_id,
            fsm_ctx.run_count,
        )
        fsm_ctx._log_state()

    signals.ingestion_completed.send(
        signals.ingestion_completed,
        event=etypes.IngestionCompleted(
            total_docs=len(files),
            total_entities=_total_entities,
            total_rels=_total_rels,
        ),
    )

    if event_log is not None:
        logger.info("event log: {} events written to {}", get_event_log_count(), event_log)

    logger.info("ingestion complete")


def _init_fsm(config, curing_enabled: bool, has_seed: bool):
    """Initialize the pipeline lifecycle FSM.

    Detects graph state from the KGFControl metanode, creates the FSM
    context, and transitions through EMPTY -> INITIALIZING -> CURING/STABLE.
    Returns None if FSM initialization fails (pipeline proceeds without FSM).
    """
    try:
        from neo4j import GraphDatabase

        from kg_builder_cli.fsm import (
            GraphState,
            create_fsm,
            detect_graph_state,
            write_run_node,
        )

        driver = GraphDatabase.driver(
            config.neo4j.uri,
            auth=(config.neo4j.user, config.neo4j.password),
        )
        try:
            detection = detect_graph_state(driver)
        finally:
            driver.close()

        logger.debug(
            "FSM detection: has_metanode={}, has_entities={}, entity_count={}, is_empty={}",
            detection["has_metanode"],
            detection["has_entities"],
            detection.get("entity_count", 0),
            detection["is_empty"],
        )

        if detection["has_metanode"]:
            meta = detection["metanode"]
            stale_fsm_state = meta.get("fsm_state")
            stale_run_id = meta.get("run_id")
            stale_consolidation = meta.get("consolidation_started_at")

            # --- Crash recovery detection ---
            force_recure = False
            loaded_names: set[str] = set()

            if stale_fsm_state == GraphState.CURING and stale_consolidation is None:
                # Scenario 1: pre-consolidation crash
                has_fluid_cache = _check_fluid_cache_exists_safe(config, meta.get("graph_id", ""))
                if has_fluid_cache:
                    # Scenario 1a: fluid cache exists -> resume accumulation
                    logger.info("previous run interrupted with fluid cache, resuming accumulation")
                else:
                    # Scenario 1b: no cache -> force re-extract
                    logger.warning("previous run interrupted without fluid cache, forcing re-cure")
                    force_recure = True

            elif stale_consolidation is not None:
                # Scenario 2: mid-consolidation crash - partial entities in graph
                wipe_count = 0
                if stale_run_id:
                    try:
                        wipe_driver = GraphDatabase.driver(
                            config.neo4j.uri,
                            auth=(config.neo4j.user, config.neo4j.password),
                        )
                        try:
                            with wipe_driver.session() as wipe_session:
                                wipe_result = wipe_session.run(
                                    "MATCH (n:Entity {run_id: $run_id}) "
                                    "WITH n LIMIT 10000 DETACH DELETE n "
                                    "RETURN count(*) AS cnt",
                                    {"run_id": stale_run_id},
                                )
                                wipe_count = wipe_result.single()["cnt"]
                        finally:
                            wipe_driver.close()
                    except Exception:
                        logger.debug("failed to wipe partial entities (non-critical)")
                # Also clean up stale fluid cache from the crashed run
                from kg_builder_cli.fsm import delete_fluid_results, delete_fluid_state

                try:
                    cache_driver = GraphDatabase.driver(
                        config.neo4j.uri,
                        auth=(config.neo4j.user, config.neo4j.password),
                    )
                    try:
                        gid = meta.get("graph_id", "")
                        delete_fluid_results(cache_driver, gid)
                        delete_fluid_state(cache_driver, gid)
                    finally:
                        cache_driver.close()
                except Exception:
                    logger.debug("failed to clean up stale fluid cache (non-critical)")
                logger.warning(
                    "previous run interrupted mid-consolidation (started_at={}), "
                    "wiped {} partial entities, forcing re-cure",
                    stale_consolidation,
                    wipe_count,
                )
                force_recure = True

            elif stale_fsm_state == GraphState.STABLE and stale_run_id is not None:
                # Scenario 3: post-consolidation crash - resume from next unloaded doc
                try:
                    resume_driver = GraphDatabase.driver(
                        config.neo4j.uri,
                        auth=(config.neo4j.user, config.neo4j.password),
                    )
                    try:
                        with resume_driver.session() as resume_session:
                            doc_result = resume_session.run(
                                "MATCH (d:Document) RETURN d.name AS name"
                            )
                            loaded_names = {r["name"] for r in doc_result}
                    finally:
                        resume_driver.close()
                except Exception:
                    logger.debug("failed to query loaded docs (non-critical)")

                logger.warning(
                    "previous run interrupted post-consolidation (run_id={}), "
                    "{} docs loaded, resuming from next unloaded",
                    stale_run_id,
                    len(loaded_names),
                )

            # Clear stale markers on metanode
            if force_recure or (stale_run_id is not None and stale_consolidation is not None):
                from kg_builder_cli.fsm import update_control_metanode as _update_meta

                stale_updates: dict[str, object] = {}
                if stale_consolidation is not None:
                    stale_updates["consolidation_started_at"] = None
                    logger.info("cleared stale consolidation marker from metanode")
                if stale_run_id is not None and force_recure:
                    stale_updates["run_id"] = None
                    logger.info("cleared stale run_id from metanode")
                if stale_updates:
                    try:
                        clear_driver = GraphDatabase.driver(
                            config.neo4j.uri,
                            auth=(config.neo4j.user, config.neo4j.password),
                        )
                        try:
                            _update_meta(clear_driver, stale_updates)
                        finally:
                            clear_driver.close()
                    except Exception:
                        logger.debug("failed to clear stale markers (non-critical)")

            initial = GraphState.STABLE
            logger.info(
                "FSM resuming existing graph: state={}, graph_id={}, run_count={}",
                meta.get("fsm_state"),
                meta.get("graph_id"),
                meta.get("run_count"),
            )
            ctx = create_fsm(
                initial_state=initial,
                graph_id=meta.get("graph_id", ""),
                run_count=meta.get("run_count", 0),
                ontology_source=meta.get("ontology_source"),
                ontology_type_count=meta.get("ontology_type_count", 0),
                ontology_hash=meta.get("ontology_hash"),
                created_at=meta.get("created_at"),
                last_completed_at=meta.get("last_completed_at"),
            )

            # Store loaded doc names for post-consolidation resume
            if not force_recure and stale_fsm_state == GraphState.STABLE and stale_run_id:
                ctx.loaded_doc_names = loaded_names

            # Force re-cure override: set curing_enabled so FSM enters CURING
            if force_recure:
                curing_enabled = True
        else:
            initial = GraphState.EMPTY
            logger.info("FSM starting fresh graph (no metanode found)")
            ctx = create_fsm(initial_state=initial)

        # Wire Neo4j config for KGFTransition audit trail writes
        ctx._neo4j_uri = config.neo4j.uri
        ctx._neo4j_user = config.neo4j.user
        ctx._neo4j_password = config.neo4j.password

        # Create metanode BEFORE transitions so audit trail nodes can link
        ctx.begin_run()
        _update_metanode_safe(config, ctx)

        # EMPTY/STABLE -> INITIALIZING
        ctx.start_run()

        # INITIALIZING -> CURING or STABLE
        if curing_enabled:
            ctx.needs_calibration = True
            ctx.extraction_mechanism = "fluid"
            ctx.ontology_source = "seed" if has_seed else "discovered"
            ctx.begin_curing()
        elif detection["has_metanode"]:
            ctx.needs_calibration = False
            ctx.begin_stable()
        else:
            ctx.needs_calibration = True
            ctx.extraction_mechanism = "direct" if has_seed else "fluid"
            ctx.ontology_source = "seed" if has_seed else "discovered"
            ctx.begin_curing()

        # Update metanode with post-transition state
        _update_metanode_safe(config, ctx)

        # Write run node
        try:
            driver = GraphDatabase.driver(
                config.neo4j.uri,
                auth=(config.neo4j.user, config.neo4j.password),
            )
            try:
                write_run_node(
                    driver,
                    run_id=ctx.run_id or "",
                    graph_id=ctx.graph_id,
                    trigger_type=ctx.extraction_mechanism,
                )
            finally:
                driver.close()
        except Exception:
            logger.debug("failed to write KGFRun node (non-critical)")

        return ctx
    except Exception as exc:
        logger.debug("FSM initialization skipped: {}", exc)
        return None


def _update_metanode_safe(config, ctx) -> None:
    """Write FSM context to KGFControl metanode. Non-critical - failures logged."""
    try:
        from neo4j import GraphDatabase

        from kg_builder_cli.fsm import create_control_metanode

        driver = GraphDatabase.driver(
            config.neo4j.uri,
            auth=(config.neo4j.user, config.neo4j.password),
        )
        try:
            create_control_metanode(
                driver,
                {
                    "graph_id": ctx.graph_id,
                    "fsm_state": ctx.state,
                    "run_id": ctx.run_id,
                    "run_count": ctx.run_count,
                    "ontology_source": ctx.ontology_source,
                    "extraction_mechanism": ctx.extraction_mechanism,
                    "consolidation_started_at": ctx.consolidation_started_at,
                    "ontology_type_count": ctx.ontology_type_count,
                    "ontology_hash": ctx.ontology_hash,
                    "created_at": ctx.created_at,
                    "last_completed_at": ctx.last_completed_at,
                    "last_error": ctx.last_error,
                },
            )
        finally:
            driver.close()
    except Exception as exc:
        logger.debug("metanode update skipped: {}", exc)


def _persist_schema_safe(config, ctx, buffer, collector=None) -> None:
    """Persist ontology schema to graph control plane nodes. Non-critical."""
    if not buffer or not ctx:
        return
    try:
        from neo4j import GraphDatabase

        from kg_builder_cli.fsm import (
            write_ontology_types,
            write_resolution_guide,
            write_type_calibration,
        )

        driver = GraphDatabase.driver(
            config.neo4j.uri,
            auth=(config.neo4j.user, config.neo4j.password),
        )
        try:
            # Write ontology type definitions
            threshold = buffer._config.min_frequency_to_confirm
            type_defs = [
                {
                    "name": td.name,
                    "description": td.description,
                    "properties": td.properties,
                }
                for td in buffer._entity_types.values()
                if buffer._frequencies.get(td.name, 0) >= threshold
            ]
            hierarchy_pairs = [
                (child, parent) for child, parent in buffer._child_to_parent.items()
            ]
            write_ontology_types(driver, ctx.graph_id, type_defs, hierarchy_pairs)

            # Write resolution guide
            if buffer._resolution_guide:
                write_resolution_guide(driver, ctx.graph_id, buffer._resolution_guide)

            # Write type calibration from observation data or entity frequencies
            obs_calibration = collector.aggregate_calibration() if collector else {}
            calibration: dict[str, dict] = {}
            for type_name in buffer._entity_types:
                freq = buffer._frequencies.get(type_name, 0)
                if freq >= threshold:
                    obs = obs_calibration.get(type_name, {})
                    calibration[type_name] = {
                        "entity_count": freq,
                        "mean_posterior": obs.get("mean_posterior", 0.0),
                        "observation_count": obs.get("observation_count", freq),
                        "remap_count": obs.get("remap_count", 0),
                        "prior_strength": 1.0,
                    }
            # Merge with existing calibration data if available
            if hasattr(buffer, "_calibration_data"):
                for type_name, data in buffer._calibration_data.items():
                    if type_name in calibration:
                        calibration[type_name].update(data)
            write_type_calibration(driver, ctx.graph_id, calibration)
        finally:
            driver.close()
    except Exception as exc:
        logger.debug("schema persistence skipped: {}", exc)


def _write_fluid_result_safe(config, fsm_ctx, doc_name: str, doc_index: int, result) -> None:
    """Cache a fluid-phase extraction result. Non-critical - failures logged."""
    if not fsm_ctx:
        return
    try:
        from neo4j import GraphDatabase

        from kg_builder_cli.fsm import write_fluid_result

        driver = GraphDatabase.driver(
            config.neo4j.uri,
            auth=(config.neo4j.user, config.neo4j.password),
        )
        try:
            write_fluid_result(
                driver, fsm_ctx.graph_id, fsm_ctx.run_id or "", doc_name, doc_index, result
            )
        finally:
            driver.close()
    except Exception as exc:
        logger.debug("fluid result cache write skipped: {}", exc)


def _write_fluid_state_safe(config, fsm_ctx, detector, metrics_tracker, deferred_buffer) -> None:
    """Cache fluid-phase detector/metrics state. Non-critical - failures logged."""
    if not fsm_ctx:
        return
    try:
        from neo4j import GraphDatabase

        from kg_builder_cli.fsm import write_fluid_state

        driver = GraphDatabase.driver(
            config.neo4j.uri,
            auth=(config.neo4j.user, config.neo4j.password),
        )
        try:
            deferred_data = deferred_buffer.to_dict() if deferred_buffer else None
            write_fluid_state(
                driver,
                fsm_ctx.graph_id,
                fsm_ctx.run_id or "",
                detector.to_dict(),
                metrics_tracker.to_dict(),
                deferred_data,
            )
        finally:
            driver.close()
    except Exception as exc:
        logger.debug("fluid state cache write skipped: {}", exc)


def _read_fluid_results_safe(config, fsm_ctx):
    """Read cached fluid results. Returns empty list on failure."""
    if not fsm_ctx:
        return []
    try:
        from neo4j import GraphDatabase

        from kg_builder_cli.fsm import read_fluid_results

        driver = GraphDatabase.driver(
            config.neo4j.uri,
            auth=(config.neo4j.user, config.neo4j.password),
        )
        try:
            return read_fluid_results(driver, fsm_ctx.graph_id)
        finally:
            driver.close()
    except Exception as exc:
        logger.debug("fluid result cache read skipped: {}", exc)
        return []


def _read_fluid_state_safe(config, fsm_ctx):
    """Read cached fluid state. Returns None on failure."""
    if not fsm_ctx:
        return None
    try:
        from neo4j import GraphDatabase

        from kg_builder_cli.fsm import read_fluid_state

        driver = GraphDatabase.driver(
            config.neo4j.uri,
            auth=(config.neo4j.user, config.neo4j.password),
        )
        try:
            return read_fluid_state(driver, fsm_ctx.graph_id)
        finally:
            driver.close()
    except Exception as exc:
        logger.debug("fluid state cache read skipped: {}", exc)
        return None


def _delete_fluid_cache_safe(config, fsm_ctx) -> None:
    """Delete all fluid cache nodes. Non-critical - failures logged."""
    if not fsm_ctx:
        return
    try:
        from neo4j import GraphDatabase

        from kg_builder_cli.fsm import delete_fluid_results, delete_fluid_state

        driver = GraphDatabase.driver(
            config.neo4j.uri,
            auth=(config.neo4j.user, config.neo4j.password),
        )
        try:
            delete_fluid_results(driver, fsm_ctx.graph_id)
            delete_fluid_state(driver, fsm_ctx.graph_id)
        finally:
            driver.close()
    except Exception as exc:
        logger.debug("fluid cache cleanup skipped: {}", exc)


def _check_fluid_cache_exists_safe(config, graph_id: str) -> bool:
    """Check if fluid cache exists. Returns False on failure."""
    try:
        from neo4j import GraphDatabase

        from kg_builder_cli.fsm import check_fluid_cache_exists

        driver = GraphDatabase.driver(
            config.neo4j.uri,
            auth=(config.neo4j.user, config.neo4j.password),
        )
        try:
            return check_fluid_cache_exists(driver, graph_id)
        finally:
            driver.close()
    except Exception:
        return False


def _ingest_direct(
    files: list[Path],
    config,
    buffer,
    *,
    fsm_ctx=None,
) -> tuple[int, int]:
    """Standard per-document ingestion with immediate Neo4j loading."""
    from kg_builder_cli.extraction.unstructured import ingest_document
    from kg_builder_cli.loading.loader import load_extraction

    run_id = fsm_ctx.run_id if fsm_ctx else None
    loaded_doc_names = fsm_ctx.loaded_doc_names if fsm_ctx else set()
    total_entities = 0
    total_rels = 0

    for i, file_path in enumerate(files):
        # Skip already-loaded documents (post-consolidation crash resume)
        if file_path.name in loaded_doc_names:
            logger.info("skipping already-loaded document: {}", file_path.name)
            continue

        logger.info("[{}/{}] processing: {}", i + 1, len(files), file_path.name)
        result = ingest_document(
            file_path,
            config,
            buffer=buffer,
            doc_index=i,
            total_docs=len(files),
            phase="direct",
        )
        total_entities += len(result.entities)
        total_rels += len(result.relationships)
        logger.info(
            "extracted {} entities, {} relationships, {} facts",
            len(result.entities),
            len(result.relationships),
            len(result.facts),
        )

        load_result = load_extraction(result, config, run_id=run_id)
        logger.info(
            "loaded: {} created, {} merged, {} relationships",
            load_result.nodes_created,
            load_result.nodes_merged,
            load_result.relationships_created,
        )

        if buffer:
            buffer._maybe_evolve()

    return total_entities, total_rels


def _ingest_fluid(
    files: list[Path],
    config,
    buffer,
    force_cure: bool = False,
    *,
    fsm_ctx=None,
) -> tuple[int, int]:
    """Two-phase ingestion: fluid accumulation then cured direct loading.

    Phase 1 (fluid): Extract and accumulate in memory, evolve schema.
    Curing event: Consolidate all accumulated results and flush to Neo4j.
    Phase 2 (cured): Remaining files load directly per-document.
    """
    from kg_builder_cli.curing.accumulator import FluidAccumulator
    from kg_builder_cli.curing.detector import CuringDetector
    from kg_builder_cli.curing.metrics import StabilityMetrics
    from kg_builder_cli.curing.observation import ObservationCollector
    from kg_builder_cli.events import signals as evt_signals
    from kg_builder_cli.events import types as etypes
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
    collector = ObservationCollector()
    calibrator = _load_calibrator_safe(config, fsm_ctx, "cross_type")

    run_id = fsm_ctx.run_id if fsm_ctx else None
    loaded_doc_names = fsm_ctx.loaded_doc_names if fsm_ctx else set()
    total_entities = 0
    total_rels = 0
    cured = False
    exemplar_index = None  # built at curing time for Bayesian resolution
    cured_type_metrics: dict | None = None  # computed at curing time for multi-channel prior

    # --- Resume from fluid cache if available ---
    cached_results = _read_fluid_results_safe(config, fsm_ctx)
    if cached_results:
        from kg_builder_cli.extraction.deferred_dedup import DeferredDedupBuffer

        for doc_name, doc_index, result in cached_results:
            accumulator.add_result(result)
            if buffer:
                buffer.accumulate_from_result(result.entities, result.relationships)
        loaded_doc_names.update(r[0] for r in cached_results)

        fluid_state = _read_fluid_state_safe(config, fsm_ctx)
        if fluid_state:
            detector = CuringDetector.from_dict(fluid_state["detector"], config.curing)
            metrics_tracker = StabilityMetrics.from_dict(fluid_state["metrics"])
            if fluid_state.get("deferred") and accumulator.deferred_buffer is not None:
                accumulator._deferred_buffer = DeferredDedupBuffer.from_dict(
                    fluid_state["deferred"]
                )

        logger.info("resumed fluid phase: {} cached docs", len(cached_results))

    for i, file_path in enumerate(files):
        # Skip already-loaded documents (post-consolidation crash resume or fluid cache)
        if file_path.name in loaded_doc_names:
            logger.info("skipping already-loaded document: {}", file_path.name)
            continue

        if cured:
            # Phase 2: direct load with graph-aware resolution
            logger.info("[cured] [{}/{}] processing: {}", i + 1, len(files), file_path.name)
            result = ingest_document(
                file_path,
                config,
                buffer=buffer,
                exemplar_index=exemplar_index,
                doc_index=i,
                total_docs=len(files),
                phase="cured",
                collector=collector,
                calibrator=calibrator,
                type_metrics=cured_type_metrics,
            )
            total_entities += len(result.entities)
            total_rels += len(result.relationships)
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
                # FSM: STABLE -> RECURING
                if fsm_ctx:
                    fsm_ctx.drift_confirmed = True
                    fsm_ctx.detect_drift()
                    _update_metanode_safe(config, fsm_ctx)

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
                    # FSM: RECURING -> CURING
                    if fsm_ctx:
                        fsm_ctx.authorize_revision()
                        fsm_ctx.needs_calibration = True
                        _update_metanode_safe(config, fsm_ctx)

                    logger.warning(
                        "[cured] DRIFT detected: re-entering fluid phase (remap rate {:.0%} for {} consecutive docs)",
                        remap_rate,
                        config.curing.drift_window,
                    )
                    cured = False
                    # Clean up stale fluid cache from previous fluid session
                    _delete_fluid_cache_safe(config, fsm_ctx)
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
                    # FSM: RECURING -> STABLE (dismiss)
                    if fsm_ctx:
                        fsm_ctx.dismiss_drift()
                        fsm_ctx.drift_confirmed = False
                        _update_metanode_safe(config, fsm_ctx)

                    logger.warning(
                        "[cured] DRIFT: {:.0%} entities remapped for {} consecutive docs",
                        remap_rate,
                        config.curing.drift_window,
                    )

            # Graph-aware resolution: remap to existing graph types
            result = resolve_against_graph(result, config)

            load_result = load_extraction(result, config, run_id=run_id)
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
        logger.info("[fluid] [{}/{}] processing: {}", i + 1, len(files), file_path.name)

        # Capture types before extraction for new type detection
        types_before = buffer.type_names() if buffer else set()

        result = ingest_document(
            file_path,
            config,
            buffer=buffer,
            doc_index=i,
            total_docs=len(files),
            phase="fluid",
            collector=collector,
            calibrator=calibrator,
        )
        total_entities += len(result.entities)
        total_rels += len(result.relationships)
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

        # Persist doc+chunks to graph immediately (enables cross-run resume)
        load_doc_chunks(result, config, run_id=run_id)
        logger.debug("[fluid] loaded doc+chunks for '{}'", file_path.name)

        # Cache extraction result and detector state to control plane
        _write_fluid_result_safe(config, fsm_ctx, file_path.name, i, result)
        _write_fluid_state_safe(
            config, fsm_ctx, detector, metrics_tracker, accumulator.deferred_buffer
        )

        # Check curing conditions
        should_cure = False
        cure_trigger = ""
        if force_cure:
            logger.warning("[fluid] force-cure requested after first document")
            should_cure = True
            cure_trigger = "force_cure"
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
                    cure_trigger = "generative"
                else:
                    logger.info("[fluid] LLM advises continue: {}", decision.reasoning)
            else:
                logger.warning("[fluid] generative curing failed, falling back to metrics")
                should_cure = _check_metric_curing(detector)
                if should_cure:
                    cure_trigger = "metric"

        # Early stopping: patience-based auto-cure
        if (
            not should_cure
            and config.curing.generative_curing
            and detector.patience_exceeded(config.curing.generative_patience)
        ):
            threshold = max(
                3, int(config.curing.max_fluid_documents * config.curing.generative_patience)
            )
            evt_signals.patience_exceeded.send(
                evt_signals.patience_exceeded,
                event=etypes.PatienceExceeded(
                    docs_processed=detector.docs_processed,
                    max_patience=threshold,
                    trigger="consecutive_cure_votes",
                ),
            )
            logger.info(
                "[fluid] EARLY STOP: {} consecutive cure votes (patience {:.0%} of {} docs)",
                threshold,
                config.curing.generative_patience,
                config.curing.max_fluid_documents,
            )
            should_cure = True
            cure_trigger = "patience"

        if not should_cure and not force_cure and not config.curing.generative_curing:
            should_cure = _check_metric_curing(detector)
            if should_cure:
                cure_trigger = "metric"

        # Safety net ALWAYS applies
        if not should_cure and detector.is_force_required():
            logger.warning(
                "[fluid] SAFETY NET: force-curing at max_fluid_documents={} (signal-based curing did not trigger)",
                config.curing.max_fluid_documents,
            )
            should_cure = True
            cure_trigger = "safety_net"

        if should_cure:
            evt_signals.curing_triggered.send(
                evt_signals.curing_triggered,
                event=etypes.CuringTriggered(
                    trigger=cure_trigger,
                    doc_index=i,
                    accumulated_docs=accumulator.doc_count,
                    type_count=len(buffer.type_names()) if buffer else 0,
                ),
            )

            # FSM: mark consolidation start for crash recovery
            if fsm_ctx:
                logger.info("FSM: consolidation starting (crash recovery marker set)")
                fsm_ctx.mark_consolidation_start()
                fsm_ctx._log_state()
                _update_metanode_safe(config, fsm_ctx)

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

            # Derive calibration ground truth and fit curves
            cured_type_metrics = _fit_and_persist_calibration(
                collector,
                type_mapping if entity_type_names else {},
                config,
                fsm_ctx,
                accumulator,
                freqs,
                buffer,
                doc_index=i,
                trigger=cure_trigger,
            )

            # Doc+chunks already loaded per-document during fluid phase

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
            load_result = load_extraction(
                merged_result, config, skip_doc_chunks=True, run_id=run_id
            )
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

            # FSM: CURING -> STABLE + schema persistence (FSC-2)
            if fsm_ctx:
                fsm_ctx.mark_consolidation_end()
                fsm_ctx.ontology_type_count = len(buffer.type_names()) if buffer else 0
                if buffer:
                    fsm_ctx.ontology_hash = buffer.compute_hash()
                    logger.info("ontology hash computed: {}", fsm_ctx.ontology_hash)
                fsm_ctx.stabilize()
                _update_metanode_safe(config, fsm_ctx)
                _persist_schema_safe(config, fsm_ctx, buffer, collector)

            # Clean up fluid cache after successful curing
            _delete_fluid_cache_safe(config, fsm_ctx)

            evt_signals.phase_transition.send(
                evt_signals.phase_transition,
                event=etypes.PhaseTransition(
                    from_phase="fluid",
                    to_phase="cured",
                    trigger=cure_trigger,
                    doc_index=i,
                ),
            )

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

        # Derive calibration ground truth and fit curves
        cured_type_metrics = _fit_and_persist_calibration(
            collector,
            type_mapping if entity_type_names else {},
            config,
            fsm_ctx,
            accumulator,
            freqs,
            buffer,
            doc_index=accumulator.doc_count - 1,
            trigger="end_of_pipeline",
        )

        # Doc+chunks already loaded per-document during fluid phase

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
        load_result = load_extraction(merged_result, config, skip_doc_chunks=True, run_id=run_id)
        logger.info(
            "[flush] loaded: {} created, {} merged, {} relationships",
            load_result.nodes_created,
            load_result.nodes_merged,
            load_result.relationships_created,
        )

        # FSM: CURING -> STABLE (end-of-corpus flush) + schema persistence (FSC-2)
        if fsm_ctx:
            fsm_ctx.mark_consolidation_end()
            fsm_ctx.ontology_type_count = len(buffer.type_names()) if buffer else 0
            if buffer:
                fsm_ctx.ontology_hash = buffer.compute_hash()
                logger.info("ontology hash computed: {}", fsm_ctx.ontology_hash)
            fsm_ctx.stabilize()
            _update_metanode_safe(config, fsm_ctx)
            _persist_schema_safe(config, fsm_ctx, buffer, collector)

        # Clean up fluid cache after end-of-corpus flush
        _delete_fluid_cache_safe(config, fsm_ctx)

    return total_entities, total_rels


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


def _load_calibrator_safe(config, fsm_ctx, model_type: str):
    """Load a calibration curve from the graph. Returns PosteriorCalibrator or None."""
    if not fsm_ctx:
        return None
    try:
        import json

        from neo4j import GraphDatabase

        from kg_builder_cli.curing.calibration import PosteriorCalibrator
        from kg_builder_cli.fsm import read_calibration_curve

        driver = GraphDatabase.driver(
            config.neo4j.uri,
            auth=(config.neo4j.user, config.neo4j.password),
        )
        try:
            data = read_calibration_curve(driver, fsm_ctx.graph_id, model_type)
            if data and data["n_samples"] >= PosteriorCalibrator._MIN_SAMPLES:
                x = json.loads(data["x_points"])
                y = json.loads(data["y_points"])
                logger.info(
                    "loaded calibration curve: model_type={}, {} points",
                    model_type,
                    len(x),
                )
                return PosteriorCalibrator(x, y)
        finally:
            driver.close()
    except Exception as exc:
        logger.debug("calibration curve load skipped: {}", exc)
    return None


def _fit_and_persist_calibration(
    collector,
    type_mapping,
    config,
    fsm_ctx,
    accumulator,
    freqs,
    buffer,
    doc_index: int = -1,
    trigger: str = "unknown",
) -> dict[str, dict[str, float]]:
    """Derive ground truth, fit calibration curves, compute type metrics, persist.

    Returns the computed type_metrics dict for use in cured-phase resolution.
    """
    from kg_builder_cli.events import signals as evt_signals
    from kg_builder_cli.events import types as etypes

    # Derive ground truth from type clustering
    gt_pairs = collector.derive_ground_truth(type_mapping)
    logger.info(
        "[calibration] {} ground truth pairs from {} cross-type obs, {} assignment obs",
        len(gt_pairs),
        collector.cross_type_count,
        collector.type_assignment_count,
    )

    # Emit ground truth event
    if gt_pairs:
        correct_count = sum(1 for _, c in gt_pairs if c)
        evt_signals.calibration_ground_truth.send(
            evt_signals.calibration_ground_truth,
            event=etypes.CalibrationGroundTruth(
                pair_count=len(gt_pairs),
                correct_count=correct_count,
                accuracy=correct_count / len(gt_pairs),
            ),
        )

    # Fit calibration curve
    if gt_pairs:
        from kg_builder_cli.curing.calibration import PosteriorCalibrator

        raw_posteriors = [p for p, _ in gt_pairs]
        labels = [c for _, c in gt_pairs]
        calibrator = PosteriorCalibrator.fit(raw_posteriors, labels)
        if calibrator:
            x_pts, y_pts = calibrator.to_points()
            evt_signals.calibration_fitted.send(
                evt_signals.calibration_fitted,
                event=etypes.CalibrationFitted(
                    n_samples=len(gt_pairs),
                    model_type="cross_type",
                    curve_points=len(x_pts),
                    x_min=min(x_pts) if x_pts else 0.0,
                    x_max=max(x_pts) if x_pts else 0.0,
                    y_min=min(y_pts) if y_pts else 0.0,
                    y_max=max(y_pts) if y_pts else 0.0,
                ),
            )
            if fsm_ctx:
                _persist_calibration_curve_safe(config, fsm_ctx, calibrator, "cross_type")

    # Aggregate observations into calibration data for KGFTypeCalibration
    obs_calibration = collector.aggregate_calibration()

    # Compute type metrics
    type_metrics = _compute_type_metrics_safe(accumulator, freqs, buffer, obs_calibration)
    if type_metrics:
        evt_signals.type_metrics_computed.send(
            evt_signals.type_metrics_computed,
            event=etypes.TypeMetricsComputed(
                type_count=len(type_metrics),
                metric_count=19,
                metrics_per_type=type_metrics,
                doc_index=doc_index,
                trigger=trigger,
            ),
        )

    # Spearman correlation: metrics vs resolution correctness
    if type_metrics and gt_pairs:
        from kg_builder_cli.curing.observation import compute_spearman_correlations

        correctness_rates = collector.compute_type_correctness_rates(type_mapping)
        correlations = compute_spearman_correlations(type_metrics, correctness_rates)
        if correlations:
            sorted_by_rho = sorted(correlations.items(), key=lambda x: x[1], reverse=True)
            top_pos = [name for name, rho in sorted_by_rho[:3] if rho > 0]
            top_neg = [name for name, rho in sorted_by_rho[-3:] if rho < 0]
            evt_signals.metric_correlation_computed.send(
                evt_signals.metric_correlation_computed,
                event=etypes.MetricCorrelationComputed(
                    n_types=len(correctness_rates),
                    correlations=correlations,
                    top_positive=top_pos,
                    top_negative=top_neg,
                ),
            )

    return type_metrics


def _compute_type_metrics_safe(accumulator, freqs, buffer, calibration_data):
    """Compute type metrics. Non-critical - returns empty dict on failure."""
    try:
        from kg_builder_cli.curing.type_metrics import TypeMetricsCollector

        results = accumulator._results if hasattr(accumulator, "_results") else []
        collector = TypeMetricsCollector(
            results=results,
            frequencies=freqs,
            calibration_data=calibration_data,
        )
        return collector.compute()
    except Exception as exc:
        logger.debug("type metrics computation skipped: {}", exc)
        return {}


def _persist_calibration_curve_safe(config, fsm_ctx, calibrator, model_type: str) -> None:
    """Persist a calibration curve to the graph. Non-critical."""
    if not fsm_ctx:
        return
    try:
        import json

        from neo4j import GraphDatabase

        from kg_builder_cli.fsm import write_calibration_curve

        x, y = calibrator.to_points()
        driver = GraphDatabase.driver(
            config.neo4j.uri,
            auth=(config.neo4j.user, config.neo4j.password),
        )
        try:
            write_calibration_curve(
                driver,
                fsm_ctx.graph_id,
                model_type,
                json.dumps(x),
                json.dumps(y),
                calibrator.n_samples,
            )
        finally:
            driver.close()
    except Exception as exc:
        logger.debug("calibration curve persist skipped: {}", exc)


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
