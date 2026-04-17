"""LLM-assisted curing and re-curing decisions.

Provides structured LLM evaluation of whether to cure (freeze ontology) or
re-cure (re-enter fluid phase on drift). The LLM receives the complete metric
history as a timeline and applies explicit decision rules. On any failure,
returns None so callers fall through to metric-based checks.

Two-phase flow: first call returns a CureProbe that may request a graph query.
If honoured, a second call with enriched context produces the final decision.
"""

from __future__ import annotations

import math
import os
from typing import TYPE_CHECKING, Literal

from loguru import logger
from pydantic import BaseModel, Field

from kgf.types.config import LLMConfig

if TYPE_CHECKING:
    from kgf.curing.accumulator import FluidAccumulator
    from kgf.types.config import Neo4jConfig


class CureProbe(BaseModel):
    """First-pass: decide or request a graph query."""

    should_cure: bool = Field(description="Your cure decision based on available data")
    reasoning: str = Field(description="Brief explanation")
    needs_query: bool = Field(
        default=False,
        description="True ONLY if metrics are ambiguous and you need graph data to verify",
    )
    query_type: Literal["entity_counts", "relationship_patterns", "entity_search"] | None = Field(
        default=None, description="Query type if needs_query is True"
    )
    query_filter_type: str | None = Field(default=None, description="Filter by entity type")
    query_filter_name: str | None = Field(
        default=None, description="Filter by entity name substring"
    )


class CureDecision(BaseModel):
    should_cure: bool = Field(description="True to cure now, False to continue fluid phase")
    reasoning: str = Field(description="Brief explanation")


class RecureDecision(BaseModel):
    should_recure: bool = Field(description="True to re-enter fluid phase, False to dismiss drift")
    reasoning: str = Field(description="Brief explanation")


def _fmt_metric(value: float, fmt: str = ".4f") -> str:
    """NaN-safe metric formatting."""
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "n/a"
    return f"{value:{fmt}}"


_CURE_PROMPT = """You are an ontology curing evaluator. Given the metric history and type list below, decide whether to CURE (freeze the ontology) or CONTINUE (keep discovering types).

**Domain intent**: {intent}
**Documents processed**: {docs_processed}
**Total entities**: {total_entities}
**Type count**: {type_count}
**Coverage (Chao1)**: {coverage}

**Type list** (sorted by frequency, descending):
{type_list}

**Metric history** (one row per document):
{metrics_table}

**Decision rules**:

CURE if ALL of these are true:
1. The type list covers the major entity categories implied by the domain intent
2. JSD has been below 0.05 for at least 2 consecutive documents in the history
3. No more than 1 new type appeared in the last 2 documents
4. Chao1 coverage is above 0.7 (most types have been discovered)

BLOCK CURE if ANY of these are true:
1. The domain intent mentions entity categories not yet represented in the type list
2. Type accumulation rate was above 1.0 in the most recent document
3. Chao1 coverage is below 0.5 (many types remain undiscovered)
4. Fewer than {min_documents} documents have been processed

**Graph query** (optional):
You may request ONE graph query if the metrics are genuinely ambiguous and you need to verify a hypothesis.
Set needs_query=True and specify query_type. Only do this if the data above is insufficient to decide.
Do NOT request a query if the metrics clearly indicate cure or continue.

Apply these rules strictly. The domain understanding in rule 1 (both blocks) is your unique contribution - judge whether the type list is semantically complete for the stated intent."""

_RECURE_PROMPT = """You are an ontology drift evaluator. Given the remap history and cured type list below, decide whether to RE-CURE (re-enter fluid phase) or DISMISS the drift.

**Domain intent**: {intent}

**Cured ontology types**: {cured_types}

**Current stability**: JSD={jsd}, entropy_delta={entropy_delta}

**Remap history** (one row per cured-phase document):
{remap_table}

**Decision rules**:

RE-CURE if ALL of these are true:
1. At least 3 distinct remapped entity types are NOT synonyms or surface variants of any cured ontology type
2. Remap rate has been above 30% for the entire remap history window
3. The remapped types represent entity categories genuinely missing from the cured ontology for the stated intent

DISMISS DRIFT if ANY of these are true:
1. The remapped types are synonyms, abbreviations, or formatting variants of existing cured types
2. Remap rate dropped below 20% in any document in the remap window
3. The remapped entities are from a single anomalous document (not a sustained trend)

Apply these rules strictly against the remap timeline data."""


def _build_metrics_table(
    metrics_history: list[dict[str, float]],
    new_types_history: list[set[str]],
) -> str:
    """Build per-document metrics timeline table."""
    header = "Doc | JSD     | Entropy D | Type Accum | Chao1 Cov | Heaps B | New Types"
    separator = "----|---------|-----------|------------|-----------|---------|----------"
    rows = [header, separator]

    for idx, metrics in enumerate(metrics_history, start=1):
        jsd = _fmt_metric(metrics.get("js_divergence", float("nan")))
        ent_d = _fmt_metric(metrics.get("entropy_shannon_delta", float("nan")))
        tar = _fmt_metric(metrics.get("type_accumulation_rate", float("nan")), ".1f")
        chao1 = _fmt_metric(metrics.get("chao1_coverage", float("nan")), ".3f")
        heaps = _fmt_metric(metrics.get("heaps_beta", float("nan")), ".3f")

        new_types = set()
        if idx - 1 < len(new_types_history):
            new_types = new_types_history[idx - 1]
        types_str = ", ".join(sorted(new_types)) if new_types else "(none)"

        rows.append(
            f"{idx:3d} | {jsd:>7s} | {ent_d:>9s} | {tar:>10s} | {chao1:>9s} | {heaps:>7s} | {types_str}"
        )

    return "\n".join(rows)


def _build_remap_table(remap_history: list[float]) -> str:
    """Build per-document remap timeline table."""
    header = "Doc | Remap Rate"
    separator = "----|----------"
    rows = [header, separator]

    for idx, rate in enumerate(remap_history, start=1):
        rows.append(f"{idx:3d} | {rate:.2%}")

    return "\n".join(rows)


def _is_ambiguous_for_query(stability: dict[str, float], coverage: float) -> bool:
    """Check if metrics are genuinely ambiguous enough to warrant a graph query.

    Returns True when JSD is in the ambiguous range (0.02-0.08) OR
    Chao1 coverage is in the uncertain range (0.5-0.75).
    """
    jsd = stability.get("js_divergence", float("nan"))
    if not math.isnan(jsd) and 0.02 <= jsd <= 0.08:
        return True
    if not math.isnan(coverage) and 0.5 <= coverage <= 0.75:
        return True
    return False


def _format_query_result(result) -> str:
    """Format a GraphQueryResult for inclusion in the LLM prompt."""
    lines = [f"**Summary**: {result.summary}"]
    if result.records:
        # Format as a simple table
        keys = list(result.records[0].keys())
        header = " | ".join(keys)
        lines.append(header)
        lines.append("-" * len(header))
        for record in result.records[:20]:
            lines.append(" | ".join(str(record.get(k, "")) for k in keys))
    return "\n".join(lines)


def llm_should_cure(
    type_names: set[str],
    frequencies: dict[str, int],
    coverage: float,
    intent: str | None,
    stability: dict[str, float],
    metrics_history: list[dict[str, float]],
    new_types_history: list[set[str]],
    docs_processed: int,
    total_entities: int,
    llm_config: LLMConfig,
    min_documents: int = 3,
    accumulator: "FluidAccumulator | None" = None,
    max_tool_calls: int = 2,
) -> CureDecision | None:
    """Ask LLM whether to cure the ontology. Returns None on failure.

    Two-phase flow: first call may request a graph query. If metrics are
    ambiguous and accumulator is available, the query is executed and a
    second call makes the final decision with enriched context.
    """
    if llm_config.region:
        os.environ["AWS_REGION_NAME"] = llm_config.region
    if llm_config.profile:
        os.environ["AWS_PROFILE"] = llm_config.profile

    # Build type list sorted by frequency descending
    sorted_types = sorted(type_names, key=lambda t: frequencies.get(t, 0), reverse=True)
    type_list = "\n".join(f"- {t}: {frequencies.get(t, 0)}" for t in sorted_types)

    metrics_table = _build_metrics_table(metrics_history, new_types_history)

    prompt = _CURE_PROMPT.format(
        intent=intent or "general knowledge graph",
        docs_processed=docs_processed,
        total_entities=total_entities,
        type_count=len(type_names),
        coverage=_fmt_metric(coverage, ".3f"),
        type_list=type_list,
        metrics_table=metrics_table,
        min_documents=min_documents,
    )

    model_id = (
        f"{llm_config.provider}/{llm_config.model}"
        if llm_config.provider == "bedrock"
        else llm_config.model
    )

    try:
        import time

        import instructor
        import litellm

        from kgf.events import signals as evt_signals
        from kgf.events import types as etypes
        from kgf.extraction.extract import extract_usage

        client = instructor.from_litellm(litellm.completion)

        # Phase 1: probe call
        evt_signals.llm_call_started.send(
            evt_signals.llm_call_started,
            event=etypes.LLMCallStarted(call_type="curing_probe", model=model_id),
        )
        t0 = time.monotonic()

        probe = client.create(
            model=model_id,
            response_model=CureProbe,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            max_retries=2,
        )

        duration_ms = int((time.monotonic() - t0) * 1000)
        usage = extract_usage(probe)
        evt_signals.llm_call_completed.send(
            evt_signals.llm_call_completed,
            event=etypes.LLMCallCompleted(
                call_type="curing_probe",
                model=model_id,
                duration_ms=duration_ms,
                token_count=usage["total_tokens"],
                prompt_tokens=usage["prompt_tokens"],
                completion_tokens=usage["completion_tokens"],
            ),
        )

        # Phase 2: optional graph query
        if (
            probe.needs_query
            and probe.query_type
            and max_tool_calls > 0
            and accumulator is not None
            and _is_ambiguous_for_query(stability, coverage)
        ):
            from kgf.curing.graph_query import GraphQueryRequest, query_fluid

            request = GraphQueryRequest(
                query_type=probe.query_type,
                filter_type=probe.query_filter_type,
                filter_name=probe.query_filter_name,
            )
            query_result = query_fluid(request, accumulator)
            logger.info(
                "Graph query executed: {} -> {} records",
                probe.query_type,
                query_result.record_count,
            )

            enriched_prompt = (
                prompt + "\n\n**Graph query result**:\n" + _format_query_result(query_result)
            )

            evt_signals.llm_call_started.send(
                evt_signals.llm_call_started,
                event=etypes.LLMCallStarted(call_type="curing_decision", model=model_id),
            )
            t0 = time.monotonic()

            decision = client.create(
                model=model_id,
                response_model=CureDecision,
                messages=[{"role": "user", "content": enriched_prompt}],
                temperature=0.0,
                max_retries=2,
            )

            duration_ms = int((time.monotonic() - t0) * 1000)
            usage = extract_usage(decision)
            evt_signals.llm_call_completed.send(
                evt_signals.llm_call_completed,
                event=etypes.LLMCallCompleted(
                    call_type="curing_decision",
                    model=model_id,
                    duration_ms=duration_ms,
                    token_count=usage["total_tokens"],
                    prompt_tokens=usage["prompt_tokens"],
                    completion_tokens=usage["completion_tokens"],
                ),
            )
            return decision

        # No query needed or not honoured - return probe decision directly
        return CureDecision(should_cure=probe.should_cure, reasoning=probe.reasoning)

    except Exception:
        logger.exception("Generative curing LLM call failed")
        return None


def llm_should_recure(
    cured_ontology_types: list[str],
    remap_history: list[float],
    recent_remap_rate: float,
    remap_count: int,
    intent: str | None,
    stability: dict[str, float],
    llm_config: LLMConfig,
    neo4j_config: "Neo4jConfig | None" = None,
) -> RecureDecision | None:
    """Ask LLM whether to re-cure on drift. Returns None on failure."""
    if llm_config.region:
        os.environ["AWS_REGION_NAME"] = llm_config.region
    if llm_config.profile:
        os.environ["AWS_PROFILE"] = llm_config.profile

    remap_table = _build_remap_table(remap_history)

    jsd = _fmt_metric(stability.get("js_divergence", float("nan")))
    ent_d = _fmt_metric(stability.get("entropy_shannon_delta", float("nan")))

    prompt = _RECURE_PROMPT.format(
        intent=intent or "general knowledge graph",
        cured_types=", ".join(sorted(cured_ontology_types)),
        jsd=jsd,
        entropy_delta=ent_d,
        remap_table=remap_table,
    )

    model_id = (
        f"{llm_config.provider}/{llm_config.model}"
        if llm_config.provider == "bedrock"
        else llm_config.model
    )

    try:
        import time

        import instructor
        import litellm

        from kgf.events import signals as evt_signals
        from kgf.events import types as etypes
        from kgf.extraction.extract import extract_usage

        client = instructor.from_litellm(litellm.completion)

        evt_signals.llm_call_started.send(
            evt_signals.llm_call_started,
            event=etypes.LLMCallStarted(call_type="recure_decision", model=model_id),
        )
        t0 = time.monotonic()

        result = client.create(
            model=model_id,
            response_model=RecureDecision,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            max_retries=2,
        )

        duration_ms = int((time.monotonic() - t0) * 1000)
        usage = extract_usage(result)
        evt_signals.llm_call_completed.send(
            evt_signals.llm_call_completed,
            event=etypes.LLMCallCompleted(
                call_type="recure_decision",
                model=model_id,
                duration_ms=duration_ms,
                token_count=usage["total_tokens"],
                prompt_tokens=usage["prompt_tokens"],
                completion_tokens=usage["completion_tokens"],
            ),
        )
        return result
    except Exception:
        logger.exception("Generative re-cure LLM call failed")
        return None
