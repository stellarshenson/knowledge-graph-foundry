"""In-memory accumulator for fluid-phase extraction results."""

from __future__ import annotations

from loguru import logger

from kg_builder_cli.extraction.dedup import deduplicate, normalize_entity_ids
from kg_builder_cli.extraction.resolution import resolve_entities, rewire_relationships
from kg_builder_cli.types.config import ExtractConfig
from kg_builder_cli.types.document import Chunk
from kg_builder_cli.types.extraction import (
    Entity,
    ExtractionResult,
    Relationship,
)
from kg_builder_cli.types.ontology import OntologyState


class FluidAccumulator:
    """Stores extraction results during the fluid phase.

    Results are accumulated per-document and consolidated into a single
    merged result when the schema cures.
    """

    def __init__(self):
        self._results: list[ExtractionResult] = []

    def add_result(self, result: ExtractionResult) -> None:
        """Append an extraction result from a document."""
        self._results.append(result)
        logger.debug(
            "Accumulated result: {} entities, {} relationships (total docs: {})",
            len(result.entities),
            len(result.relationships),
            len(self._results),
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
    ) -> ExtractionResult:
        """Consolidate all accumulated results into a single merged result.

        Steps:
        1. Enforce ontology types (remap to cured ontology)
        2. Normalize entity IDs for cross-document merging
        3. Deduplicate
        4. Resolve entities (multi-signal merge)
        5. Rewire relationships
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
            from kg_builder_cli.extraction.unstructured import _enforce_ontology_types

            allowed = [t.name for t in ontology.entity_types]
            entities, _ = _enforce_ontology_types(entities, allowed)

        # Step 2: Normalize entity IDs
        entities, relationships = normalize_entity_ids(entities, relationships)

        # Step 3: Deduplicate
        entities, relationships = deduplicate(entities, relationships)

        # Step 4: Entity resolution
        entities = resolve_entities(
            entities,
            threshold=config.resolution_threshold,
            use_embeddings=config.use_embeddings,
            embedding_threshold=config.embedding_threshold,
            name_threshold=config.name_threshold,
            type_frequencies=type_frequencies,
            cross_type_embedding_threshold=config.cross_type_embedding_threshold,
        )

        # Step 5: Rewire relationships
        id_map = getattr(resolve_entities, "_last_id_map", {})
        if id_map:
            relationships = rewire_relationships(relationships, id_map)

        logger.info(
            "Consolidation complete: {} entities, {} relationships",
            len(entities),
            len(relationships),
        )

        return ExtractionResult(
            entities=entities,
            relationships=relationships,
            chunks=chunks,
        )
