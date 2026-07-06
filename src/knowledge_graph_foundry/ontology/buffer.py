"""Fluid ontology buffer - accumulates extraction results while the schema
is fluid and self-evolves after every document.

v1 lesson baked in: evolution counts ENCOUNTERS (entity occurrences), not
documents, and runs after every document - a bolted-on post-ingestion pass
was completely inert. The buffer is serializable so the graph metanode can
cache it for resume.
"""

from __future__ import annotations

from collections import Counter

from knowledge_graph_foundry.events import emit
from knowledge_graph_foundry.models import (
    Entity,
    Ontology,
    Relationship,
    RelationshipTypeDef,
    TypeDef,
)
from knowledge_graph_foundry.settings import CuringSettings


class FluidBuffer:
    def __init__(self, ontology: Ontology, cfg: CuringSettings):
        self.ontology = ontology
        self.cfg = cfg
        self.entities: list[Entity] = []
        self.relationships: list[Relationship] = []
        self.documents_processed: int = 0

    def add_document(self, entities: list[Entity], relationships: list[Relationship]) -> None:
        """Append one document's extraction output and evolve the ontology."""
        self.entities.extend(entities)
        self.relationships.extend(relationships)
        self.documents_processed += 1
        self._evolve(entities, relationships)

    def _evolve(self, entities: list[Entity], relationships: list[Relationship]) -> None:
        """Per-encounter evolution: count type encounters, confirm emerging types."""
        for entity in entities:
            for type_name in entity.types:
                if type_name not in self.ontology.types:
                    self.ontology.types[type_name] = TypeDef(name=type_name)
                    emit("ontology.type_emerged", type=type_name)
                self.ontology.types[type_name].encounters += 1

        for rel in relationships:
            if rel.type not in self.ontology.relationship_types:
                self.ontology.relationship_types[rel.type] = RelationshipTypeDef(name=rel.type)
            self.ontology.relationship_types[rel.type].encounters += 1

        for type_def in self.ontology.types.values():
            if (
                type_def.status == "emerging"
                and type_def.encounters >= self.cfg.min_encounters_to_confirm
            ):
                type_def.status = "confirmed"
                emit("ontology.type_confirmed", type=type_def.name)

        emit(
            "ontology.evolved",
            documents=self.documents_processed,
            types=len(self.ontology.types),
            entities=len(self.entities),
        )

    def type_frequencies(self) -> dict[str, int]:
        """Entity-occurrence counts per type, feeding the stability metrics."""
        counts: Counter[str] = Counter()
        for entity in self.entities:
            for type_name in entity.types:
                counts[type_name] += 1
        return dict(counts)

    def to_dict(self) -> dict:
        return {
            "ontology": self.ontology.model_dump(),
            "entities": [e.model_dump() for e in self.entities],
            "relationships": [r.model_dump() for r in self.relationships],
            "documents_processed": self.documents_processed,
        }

    @classmethod
    def from_dict(cls, data: dict, cfg: CuringSettings) -> "FluidBuffer":
        buffer = cls(Ontology(**data["ontology"]), cfg)
        buffer.entities = [Entity(**e) for e in data.get("entities", [])]
        buffer.relationships = [Relationship(**r) for r in data.get("relationships", [])]
        buffer.documents_processed = data.get("documents_processed", 0)
        return buffer
