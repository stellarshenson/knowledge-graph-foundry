"""Deferred cross-type deduplication with evidence accumulation and LLM escalation.

Ambiguous cross-type entity pairs (posterior 0.4-0.6) are deferred during the
fluid phase instead of being permanently blocked. Evidence accumulates across
documents (co-occurrence, relationship overlap, descriptions). At curing time,
pairs are resolved with accumulated evidence and optional LLM escalation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal

from loguru import logger

from knowledge_graph_foundry.events import signals as evt_signals
from knowledge_graph_foundry.events import types as etypes
from knowledge_graph_foundry.extraction.normalization import normalize_entity_name
from knowledge_graph_foundry.types.extraction import Entity, Relationship

if TYPE_CHECKING:
    from knowledge_graph_foundry.types.config import LLMConfig, Neo4jConfig


@dataclass
class DeferredPair:
    """An ambiguous cross-type entity pair awaiting more evidence."""

    entity_a_name: str  # normalized name
    type_a: str
    type_b: str
    posteriors: list[float] = field(default_factory=list)
    shared_chunks: int = 0
    shared_targets: set[str] = field(default_factory=set)
    first_seen_doc: int = 0
    last_seen_doc: int = 0
    descriptions_a: list[str] = field(default_factory=list)
    descriptions_b: list[str] = field(default_factory=list)


@dataclass
class MergeDecision:
    """Resolution decision for a deferred pair."""

    entity_name: str
    type_a: str
    type_b: str
    action: Literal["merge", "block"]
    chosen_type: str | None = None
    reasoning: str = ""
    final_posterior: float = 0.0


class DeferredDedupBuffer:
    """Accumulates ambiguous cross-type pairs during fluid phase.

    Pairs with posteriors in the ambiguous zone (lower <= p < merge_threshold)
    are deferred rather than permanently blocked. Evidence accumulates as more
    documents are processed. At curing time, pairs are resolved with the full
    evidence picture.
    """

    def __init__(self):
        # Key: (normalized_name, sorted type pair) -> DeferredPair
        self._pairs: dict[tuple[str, str, str], DeferredPair] = {}

    @property
    def pair_count(self) -> int:
        return len(self._pairs)

    def _make_key(self, norm_name: str, type_a: str, type_b: str) -> tuple[str, str, str]:
        """Create a canonical key with sorted types for consistent lookup."""
        t1, t2 = sorted([type_a, type_b])
        return (norm_name, t1, t2)

    def defer(
        self,
        canonical: Entity,
        other: Entity,
        posterior: float,
        doc_index: int,
    ) -> None:
        """Defer an ambiguous cross-type pair for later resolution.

        Called from _resolve_cross_type() when posterior is in the ambiguous zone.
        """
        norm_name = normalize_entity_name(canonical.name)
        key = self._make_key(norm_name, canonical.type, other.type)

        if key in self._pairs:
            pair = self._pairs[key]
            pair.posteriors.append(posterior)
            pair.last_seen_doc = doc_index
            # Accumulate descriptions
            if canonical.description and canonical.description not in pair.descriptions_a:
                pair.descriptions_a.append(canonical.description)
            if other.description and other.description not in pair.descriptions_b:
                pair.descriptions_b.append(other.description)
            # Accumulate shared chunks
            shared = set(canonical.source_chunks) & set(other.source_chunks)
            pair.shared_chunks += len(shared)
        else:
            self._pairs[key] = DeferredPair(
                entity_a_name=norm_name,
                type_a=canonical.type,
                type_b=other.type,
                posteriors=[posterior],
                shared_chunks=len(set(canonical.source_chunks) & set(other.source_chunks)),
                first_seen_doc=doc_index,
                last_seen_doc=doc_index,
                descriptions_a=([canonical.description] if canonical.description else []),
                descriptions_b=([other.description] if other.description else []),
            )

        logger.debug(
            "[deferred] Deferred cross-type pair: '{}' ({} vs {}) posterior={:.3f} encounters={}",
            norm_name,
            canonical.type,
            other.type,
            posterior,
            len(self._pairs[key].posteriors),
        )

    def update_evidence(
        self,
        entities: list[Entity],
        relationships: list[Relationship],
        doc_index: int,
    ) -> None:
        """Update evidence for deferred pairs from a new document's extraction.

        Called after each document extraction to accumulate:
        - New co-occurrences (shared source chunks)
        - Relationship target overlap (topology signal)
        - Updated descriptions
        """
        if not self._pairs:
            return

        # Index entities by normalized name for quick lookup
        name_to_entities: dict[str, list[Entity]] = {}
        for e in entities:
            norm = normalize_entity_name(e.name)
            name_to_entities.setdefault(norm, []).append(e)

        # Index relationship targets by entity ID
        entity_targets: dict[str, set[str]] = {}
        for rel in relationships:
            entity_targets.setdefault(rel.source, set()).add(rel.target)
            entity_targets.setdefault(rel.target, set()).add(rel.source)

        for key, pair in self._pairs.items():
            norm_name = pair.entity_a_name
            if norm_name not in name_to_entities:
                continue

            matching = name_to_entities[norm_name]

            # Find entities matching each type in the pair
            type_a_entities = [e for e in matching if e.type == pair.type_a]
            type_b_entities = [e for e in matching if e.type == pair.type_b]

            if not type_a_entities and not type_b_entities:
                continue

            pair.last_seen_doc = doc_index

            # Accumulate shared chunks between types
            chunks_a = {c for e in type_a_entities for c in e.source_chunks}
            chunks_b = {c for e in type_b_entities for c in e.source_chunks}
            new_shared = len(chunks_a & chunks_b)
            if new_shared > 0:
                pair.shared_chunks += new_shared

            # Accumulate relationship target overlap (topology signal)
            targets_a: set[str] = set()
            for e in type_a_entities:
                targets_a.update(entity_targets.get(e.id, set()))
            targets_b: set[str] = set()
            for e in type_b_entities:
                targets_b.update(entity_targets.get(e.id, set()))
            pair.shared_targets.update(targets_a & targets_b)

            # Accumulate descriptions
            for e in type_a_entities:
                if e.description and e.description not in pair.descriptions_a:
                    pair.descriptions_a.append(e.description)
            for e in type_b_entities:
                if e.description and e.description not in pair.descriptions_b:
                    pair.descriptions_b.append(e.description)

            # Emit evidence update signal for pairs touched this document
            if pair.last_seen_doc == doc_index:
                _targets_a: set[str] = set()
                for e in type_a_entities:
                    _targets_a.update(entity_targets.get(e.id, set()))
                _targets_b: set[str] = set()
                for e in type_b_entities:
                    _targets_b.update(entity_targets.get(e.id, set()))
                _all_targets = _targets_a | _targets_b
                evt_signals.deferred_evidence_updated.send(
                    evt_signals.deferred_evidence_updated,
                    event=etypes.DeferredEvidenceUpdated(
                        entity_name=pair.entity_a_name,
                        type_a=pair.type_a,
                        type_b=pair.type_b,
                        shared_chunks=pair.shared_chunks,
                        topology_jaccard=(
                            len(pair.shared_targets) / max(len(_all_targets), 1)
                            if _all_targets
                            else 0.0
                        ),
                        posteriors_count=len(pair.posteriors),
                        desc_similarity=0.0,
                    ),
                )

    def to_dict(self) -> dict:
        """Serialize deferred buffer for cross-run persistence."""
        pairs = {}
        for key, pair in self._pairs.items():
            str_key = f"{key[0]}|{key[1]}|{key[2]}"
            pairs[str_key] = {
                "entity_a_name": pair.entity_a_name,
                "type_a": pair.type_a,
                "type_b": pair.type_b,
                "posteriors": pair.posteriors,
                "shared_chunks": pair.shared_chunks,
                "shared_targets": sorted(pair.shared_targets),
                "first_seen_doc": pair.first_seen_doc,
                "last_seen_doc": pair.last_seen_doc,
                "descriptions_a": pair.descriptions_a,
                "descriptions_b": pair.descriptions_b,
            }
        return {"pairs": pairs}

    @classmethod
    def from_dict(cls, data: dict) -> DeferredDedupBuffer:
        """Restore deferred buffer from serialized state."""
        buf = cls()
        for str_key, pdata in data.get("pairs", {}).items():
            parts = str_key.split("|", 2)
            key = (parts[0], parts[1], parts[2])
            buf._pairs[key] = DeferredPair(
                entity_a_name=pdata["entity_a_name"],
                type_a=pdata["type_a"],
                type_b=pdata["type_b"],
                posteriors=pdata.get("posteriors", []),
                shared_chunks=pdata.get("shared_chunks", 0),
                shared_targets=set(pdata.get("shared_targets", [])),
                first_seen_doc=pdata.get("first_seen_doc", 0),
                last_seen_doc=pdata.get("last_seen_doc", 0),
                descriptions_a=pdata.get("descriptions_a", []),
                descriptions_b=pdata.get("descriptions_b", []),
            )
        return buf

    def resolve_all(
        self,
        type_frequencies: dict[str, int] | None = None,
        llm_config: "LLMConfig | None" = None,
        neo4j_config: "Neo4jConfig | None" = None,
        llm_escalation: bool = False,
    ) -> list[MergeDecision]:
        """Resolve all deferred pairs at curing time.

        For each pair:
        1. Recompute posterior with accumulated evidence + topology signal
        2. If still ambiguous and llm_escalation=True, escalate to LLM
        3. Return merge/block decisions

        Returns list of MergeDecision for caller to apply.
        """
        if not self._pairs:
            return []

        from knowledge_graph_foundry.extraction.resolution import (
            _build_type_priority,
            _description_similarity,
        )

        type_priority = _build_type_priority(type_frequencies)
        decisions: list[MergeDecision] = []

        for key, pair in self._pairs.items():
            # Recompute posterior with accumulated evidence
            avg_posterior = sum(pair.posteriors) / len(pair.posteriors) if pair.posteriors else 0.0

            # Topology signal: Jaccard overlap of relationship targets
            topology_boost = 0.0
            if pair.shared_targets:
                # Estimate total targets from description count as proxy
                # More shared targets = stronger merge signal
                topology_boost = min(len(pair.shared_targets) * 0.05, 0.15)

            # Co-occurrence boost: accumulated shared chunks
            cooc_boost = min(pair.shared_chunks * 0.02, 0.1)

            # Description evidence: cross-description similarity
            desc_boost = 0.0
            if pair.descriptions_a and pair.descriptions_b:
                max_sim = 0.0
                for da in pair.descriptions_a:
                    for db in pair.descriptions_b:
                        sim = _description_similarity(da, db)
                        max_sim = max(max_sim, sim)
                desc_boost = max_sim * 0.1

            final_posterior = avg_posterior + topology_boost + cooc_boost + desc_boost
            final_posterior = min(final_posterior, 0.99)

            # Determine winning type
            prio_a = type_priority.get(pair.type_a, 0)
            prio_b = type_priority.get(pair.type_b, 0)
            chosen_type = pair.type_a if prio_a >= prio_b else pair.type_b

            if final_posterior >= 0.6:
                decisions.append(
                    MergeDecision(
                        entity_name=pair.entity_a_name,
                        type_a=pair.type_a,
                        type_b=pair.type_b,
                        action="merge",
                        chosen_type=chosen_type,
                        reasoning=(
                            f"accumulated posterior {final_posterior:.3f} >= 0.6 "
                            f"(avg={avg_posterior:.3f}, topo=+{topology_boost:.3f}, "
                            f"cooc=+{cooc_boost:.3f}, desc=+{desc_boost:.3f})"
                        ),
                        final_posterior=final_posterior,
                    )
                )
                logger.info(
                    "[deferred] MERGE '{}' ({} -> {}) posterior={:.3f} "
                    "encounters={} shared_targets={}",
                    pair.entity_a_name,
                    pair.type_b,
                    chosen_type,
                    final_posterior,
                    len(pair.posteriors),
                    len(pair.shared_targets),
                )
            elif (
                llm_escalation
                and llm_config
                and 0.4 <= final_posterior < 0.6
                and len(pair.posteriors) >= 2
            ):
                # LLM escalation for genuinely ambiguous pairs seen multiple times
                decision = self._llm_resolve_pair(
                    pair, final_posterior, chosen_type, llm_config, neo4j_config
                )
                decisions.append(decision)
            else:
                decisions.append(
                    MergeDecision(
                        entity_name=pair.entity_a_name,
                        type_a=pair.type_a,
                        type_b=pair.type_b,
                        action="block",
                        reasoning=(
                            f"accumulated posterior {final_posterior:.3f} < 0.6 "
                            f"after {len(pair.posteriors)} encounters"
                        ),
                        final_posterior=final_posterior,
                    )
                )
                logger.info(
                    "[deferred] BLOCK '{}' ({} vs {}) posterior={:.3f} encounters={}",
                    pair.entity_a_name,
                    pair.type_a,
                    pair.type_b,
                    final_posterior,
                    len(pair.posteriors),
                )
                evt_signals.deferred_pair_skipped.send(
                    evt_signals.deferred_pair_skipped,
                    event=etypes.DeferredPairSkipped(
                        entity_name=pair.entity_a_name,
                        type_a=pair.type_a,
                        type_b=pair.type_b,
                        final_posterior=final_posterior,
                        reason=(
                            f"posterior {final_posterior:.3f} < 0.6 "
                            f"after {len(pair.posteriors)} encounters"
                        ),
                    ),
                )

        merge_count = sum(1 for d in decisions if d.action == "merge")
        block_count = sum(1 for d in decisions if d.action == "block")
        logger.info(
            "[deferred] Resolved {} deferred pairs: {} merge, {} block",
            len(decisions),
            merge_count,
            block_count,
        )

        evt_signals.deferred_resolution_completed.send(
            evt_signals.deferred_resolution_completed,
            event=etypes.DeferredResolutionCompleted(
                pairs_resolved=len(decisions),
                merges=merge_count,
                blocks=block_count,
                llm_escalations=sum(1 for d in decisions if "LLM" in d.reasoning),
            ),
        )

        return decisions

    def _llm_resolve_pair(
        self,
        pair: DeferredPair,
        posterior: float,
        default_chosen_type: str,
        llm_config: "LLMConfig",
        neo4j_config: "Neo4jConfig | None",
    ) -> MergeDecision:
        """Use LLM to resolve an ambiguous deferred pair.

        Follows the instructor+litellm pattern from type_resolver.py._llm_resolve().
        """
        try:
            import time

            import instructor
            import litellm

            from knowledge_graph_foundry.events import signals as evt_signals
            from knowledge_graph_foundry.events import types as etypes
            from knowledge_graph_foundry.extraction.extract import extract_usage
            from knowledge_graph_foundry.extraction.unstructured import (
                _configure_aws_env,
                _litellm_model_id,
            )

            _configure_aws_env(llm_config)
            model_id = _litellm_model_id(llm_config)
            client = instructor.from_litellm(litellm.completion)

            # Build descriptions context
            descs_a = "; ".join(pair.descriptions_a[:3]) if pair.descriptions_a else "none"
            descs_b = "; ".join(pair.descriptions_b[:3]) if pair.descriptions_b else "none"

            prompt = (
                f"An entity '{pair.entity_a_name}' appears in a knowledge graph as two "
                f"different types:\n\n"
                f"Type A: {pair.type_a}\n"
                f"  Descriptions: {descs_a}\n\n"
                f"Type B: {pair.type_b}\n"
                f"  Descriptions: {descs_b}\n\n"
                f"Evidence: seen in {len(pair.posteriors)} documents, "
                f"{pair.shared_chunks} shared chunks, "
                f"{len(pair.shared_targets)} shared relationship targets.\n"
                f"Bayesian posterior: {posterior:.3f} (ambiguous zone).\n\n"
                f"Should these be merged into a single entity? If yes, which type "
                f"is more appropriate?\n"
                f"Consider: are these genuinely the same real-world concept viewed "
                f"from different perspectives, or are they truly different things "
                f"that happen to share a name?"
            )

            # Graph enrichment when Neo4j is available
            if neo4j_config is not None:
                from knowledge_graph_foundry.curing.graph_query import (
                    GraphQueryRequest,
                    query_graph,
                )

                request = GraphQueryRequest(
                    query_type="entity_search",
                    filter_name=pair.entity_a_name,
                )
                try:
                    result = query_graph(request, neo4j_config)
                    if result.records:
                        graph_ctx = "\n".join(
                            f"  - {r['name']} (type: {r['type']})" for r in result.records[:5]
                        )
                        prompt += (
                            f"\n\nExisting graph entities matching "
                            f"'{pair.entity_a_name}':\n{graph_ctx}"
                        )
                except Exception:
                    logger.debug(
                        "Graph query failed during deferred LLM escalation for '{}'",
                        pair.entity_a_name,
                    )

            from pydantic import BaseModel as _BM

            class _CrossTypeMergeDecision(_BM):
                should_merge: bool
                chosen_type: str
                reasoning: str = ""

            evt_signals.llm_call_started.send(
                evt_signals.llm_call_started,
                event=etypes.LLMCallStarted(
                    call_type="deferred_dedup_escalation",
                    model=model_id,
                    context={"entity_name": pair.entity_a_name},
                ),
            )
            t0 = time.monotonic()

            response = client.chat.completions.create(
                model=model_id,
                response_model=_CrossTypeMergeDecision,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
                max_retries=1,
            )

            duration_ms = int((time.monotonic() - t0) * 1000)
            usage = extract_usage(response)
            evt_signals.llm_call_completed.send(
                evt_signals.llm_call_completed,
                event=etypes.LLMCallCompleted(
                    call_type="deferred_dedup_escalation",
                    model=model_id,
                    duration_ms=duration_ms,
                    token_count=usage["total_tokens"],
                    prompt_tokens=usage["prompt_tokens"],
                    completion_tokens=usage["completion_tokens"],
                ),
            )

            action = "merge" if response.should_merge else "block"
            chosen = response.chosen_type if response.should_merge else None

            # Validate chosen type
            if chosen and chosen not in (pair.type_a, pair.type_b):
                logger.warning(
                    "[deferred] LLM returned invalid type '{}', using default '{}'",
                    chosen,
                    default_chosen_type,
                )
                chosen = default_chosen_type

            logger.info(
                "[deferred] LLM resolved '{}' ({} vs {}): {} -> {} reason: {}",
                pair.entity_a_name,
                pair.type_a,
                pair.type_b,
                action,
                chosen or "n/a",
                response.reasoning[:100],
            )

            return MergeDecision(
                entity_name=pair.entity_a_name,
                type_a=pair.type_a,
                type_b=pair.type_b,
                action=action,
                chosen_type=chosen,
                reasoning=f"LLM: {response.reasoning}",
                final_posterior=posterior,
            )

        except Exception as exc:
            logger.warning(
                "[deferred] LLM escalation failed for '{}': {}",
                pair.entity_a_name,
                exc,
            )
            return MergeDecision(
                entity_name=pair.entity_a_name,
                type_a=pair.type_a,
                type_b=pair.type_b,
                action="block",
                reasoning=f"LLM escalation failed: {exc}",
                final_posterior=posterior,
            )
