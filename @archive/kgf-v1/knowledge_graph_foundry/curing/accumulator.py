"""In-memory accumulator for fluid-phase extraction results."""

from __future__ import annotations

from loguru import logger

from knowledge_graph_foundry.extraction.dedup import deduplicate, normalize_entity_ids
from knowledge_graph_foundry.extraction.deferred_dedup import DeferredDedupBuffer
from knowledge_graph_foundry.extraction.resolution import resolve_entities, rewire_relationships
from knowledge_graph_foundry.types.config import ExtractConfig
from knowledge_graph_foundry.types.document import Chunk
from knowledge_graph_foundry.types.extraction import (
    Entity,
    ExtractionResult,
    Relationship,
)
from knowledge_graph_foundry.types.ontology import OntologyState


class FluidAccumulator:
    """Stores extraction results during the fluid phase.

    Results are accumulated per-document and consolidated into a single
    merged result when the schema cures.
    """

    def __init__(self, deferred_dedup: bool = False):
        self._results: list[ExtractionResult] = []
        self._deferred_buffer: DeferredDedupBuffer | None = (
            DeferredDedupBuffer() if deferred_dedup else None
        )

    @property
    def deferred_buffer(self) -> DeferredDedupBuffer | None:
        return self._deferred_buffer

    def add_result(self, result: ExtractionResult) -> None:
        """Append an extraction result from a document."""
        self._results.append(result)
        logger.debug(
            "Accumulated result: {} entities, {} relationships (total docs: {})",
            len(result.entities),
            len(result.relationships),
            len(self._results),
        )

        # Update deferred buffer evidence with new document's data
        if self._deferred_buffer is not None:
            self._deferred_buffer.update_evidence(
                result.entities,
                result.relationships,
                doc_index=len(self._results) - 1,
            )

    def all_entities(self) -> list[Entity]:
        """Return flattened entities from all accumulated results."""
        return [e for r in self._results for e in r.entities]

    def all_relationships(self) -> list[Relationship]:
        """Return flattened relationships from all accumulated results."""
        return [r for result in self._results for r in result.relationships]

    def all_chunks(self) -> list[Chunk]:
        """Return flattened chunks from all accumulated results."""
        return [c for r in self._results for c in r.chunks]

    @property
    def doc_count(self) -> int:
        return len(self._results)

    def consolidate(
        self,
        ontology: OntologyState,
        config: ExtractConfig,
        type_frequencies: dict[str, int] | None = None,
        skip_type_enforcement: bool = False,
        llm_config=None,
        neo4j_config=None,
    ) -> ExtractionResult:
        """Consolidate all accumulated results into a single merged result.

        Steps:
        1. Enforce ontology types (remap to cured ontology)
        2. Normalize entity IDs for cross-document merging
        3. Deduplicate
        4. Resolve entities (multi-signal merge, defers ambiguous cross-type pairs)
        5. Rewire relationships from Step 4
        6. Resolve deferred cross-type pairs (accumulated evidence + optional LLM)
        7. Rewire relationships from Step 6
        """
        entities = self.all_entities()
        relationships = self.all_relationships()
        chunks = self.all_chunks()

        logger.info(
            "Consolidating {} entities, {} relationships from {} documents",
            len(entities),
            len(relationships),
            len(self._results),
        )

        # Step 1: Enforce ontology types (skip when caller already ran clustering)
        if ontology.entity_types and not skip_type_enforcement:
            from knowledge_graph_foundry.extraction.unstructured import _enforce_ontology_types

            allowed = [t.name for t in ontology.entity_types]
            entities, remap_count = _enforce_ontology_types(entities, allowed)

            from knowledge_graph_foundry.events import signals as evt_signals
            from knowledge_graph_foundry.events import types as etypes

            evt_signals.type_enforcement_applied.send(
                evt_signals.type_enforcement_applied,
                event=etypes.TypeEnforcementApplied(
                    document_source="consolidation",
                    remap_count=remap_count,
                    method="levenshtein",
                ),
            )

        # Step 2: Normalize entity IDs
        entities, relationships = normalize_entity_ids(entities, relationships)

        # Step 3: Deduplicate
        entities, relationships = deduplicate(entities, relationships)

        # Step 4: Entity resolution (defers ambiguous cross-type pairs to buffer)
        resolution = resolve_entities(
            entities,
            threshold=config.resolution_threshold,
            use_embeddings=config.use_embeddings,
            embedding_threshold=config.embedding_threshold,
            name_threshold=config.name_threshold,
            type_frequencies=type_frequencies,
            cross_type_merge_threshold=config.cross_type_merge_threshold,
            deferred_buffer=self._deferred_buffer,
            deferred_ambiguous_lower=config.deferred_dedup_ambiguous_lower,
            ontology_state=ontology,
            hierarchy_resolution=config.hierarchy_resolution,
        )
        entities = resolution.entities

        # Step 5: Rewire relationships from Step 4 merges
        if resolution.id_map:
            relationships = rewire_relationships(relationships, resolution.id_map)

        # Step 6: Resolve deferred cross-type pairs (after Step 4 populated the buffer)
        if self._deferred_buffer and self._deferred_buffer.pair_count > 0:
            decisions = self._deferred_buffer.resolve_all(
                type_frequencies=type_frequencies,
                llm_config=llm_config,
                neo4j_config=neo4j_config,
                llm_escalation=config.deferred_dedup_llm_escalation,
            )
            entities, deferred_id_map = _apply_deferred_decisions(
                entities, decisions, type_frequencies
            )
            # Step 7: Rewire relationships from deferred merges
            if deferred_id_map:
                relationships = rewire_relationships(relationships, deferred_id_map)

        logger.info(
            "Consolidation complete: {} entities, {} relationships",
            len(entities),
            len(relationships),
        )

        from knowledge_graph_foundry.events import signals
        from knowledge_graph_foundry.events import types as etypes

        signals.consolidation_completed.send(
            signals.consolidation_completed,
            event=etypes.ConsolidationCompleted(
                entities_before=len(self.all_entities()),
                entities_after=len(entities),
                rels_before=len(self.all_relationships()),
                rels_after=len(relationships),
                deferred_resolved=(
                    self._deferred_buffer.pair_count if self._deferred_buffer else 0
                ),
                steps_completed=[
                    "type_enforcement",
                    "normalize_ids",
                    "deduplicate",
                    "entity_resolution",
                    "rewire",
                    "deferred_resolution",
                ],
            ),
        )

        return ExtractionResult(
            entities=entities,
            relationships=relationships,
            chunks=chunks,
        )


def _apply_deferred_decisions(
    entities: list[Entity],
    decisions: list,
    type_frequencies: dict[str, int] | None = None,
) -> tuple[list[Entity], dict[str, str]]:
    """Apply deferred dedup merge decisions to the entity list.

    For each merge decision, find entities matching the name and types,
    merge the lower-priority entity into the chosen type's entity.
    Returns (updated_entities, id_map) for relationship rewiring.
    """
    from knowledge_graph_foundry.extraction.normalization import normalize_entity_name
    from knowledge_graph_foundry.extraction.resolution import _merge_entities

    merge_decisions = [d for d in decisions if d.action == "merge" and d.chosen_type]
    if not merge_decisions:
        return entities, {}

    # Index entities by normalized name
    name_to_indices: dict[str, list[int]] = {}
    for idx, e in enumerate(entities):
        norm = normalize_entity_name(e.name)
        name_to_indices.setdefault(norm, []).append(idx)

    merged_indices: set[int] = set()
    id_map: dict[str, str] = {}

    for decision in merge_decisions:
        indices = name_to_indices.get(decision.entity_name, [])
        if len(indices) <= 1:
            continue

        # Find entities matching the two types in the decision
        type_a_idx = [i for i in indices if entities[i].type == decision.type_a]
        type_b_idx = [i for i in indices if entities[i].type == decision.type_b]

        if not type_a_idx or not type_b_idx:
            continue

        # Determine winner and loser based on chosen_type
        if decision.chosen_type == decision.type_a:
            winner_idx = type_a_idx[0]
            loser_indices = type_b_idx
        else:
            winner_idx = type_b_idx[0]
            loser_indices = type_a_idx

        winner = entities[winner_idx].model_copy()
        for li in loser_indices:
            id_map[entities[li].id] = winner.id
            winner = _merge_entities(winner, entities[li])
            merged_indices.add(li)
        entities[winner_idx] = winner

        logger.info(
            "[deferred] Applied merge: '{}' ({} + {}) -> {} (merged {} entities)",
            decision.entity_name,
            decision.type_a,
            decision.type_b,
            decision.chosen_type,
            len(loser_indices),
        )

    # Build result without merged entities
    result = [e for idx, e in enumerate(entities) if idx not in merged_indices]

    if merged_indices:
        logger.info(
            "[deferred] Applied {} deferred merges, removed {} entities",
            len(merge_decisions),
            len(merged_indices),
        )

    return result, id_map
