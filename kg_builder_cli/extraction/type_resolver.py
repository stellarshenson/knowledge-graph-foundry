"""Bayesian type resolver for post-extraction type assignment."""

from __future__ import annotations

from dataclasses import dataclass, field
import math

from loguru import logger

from kg_builder_cli.extraction.exemplar_index import ExemplarIndex
from kg_builder_cli.types.config import OntologyBufferConfig
from kg_builder_cli.types.extraction import Entity, Relationship


@dataclass
class ResolverContext:
    """Context for resolving a single entity's type."""

    relationships: list[Relationship] = field(default_factory=list)
    chunk_entities: list[Entity] = field(default_factory=list)
    entity_embedding: list[float] | None = None


class BayesianTypeResolver:
    """Resolve entity types using Bayesian inference over multiple evidence signals.

    Prior: normalized type frequencies from the ontology buffer.
    Likelihoods: exemplar similarity and relationship context.
    """

    def __init__(
        self,
        config: OntologyBufferConfig,
        type_frequencies: dict[str, int],
        exemplar_index: ExemplarIndex | None = None,
    ):
        self._top_k = config.type_resolution_top_k
        self._entropy_threshold = config.type_resolution_entropy_threshold
        self._prior = self._build_prior(type_frequencies)
        self._index = exemplar_index

    def _build_prior(self, type_frequencies: dict[str, int]) -> dict[str, float]:
        """Build prior P(type) from normalized type frequencies."""
        total = sum(type_frequencies.values())
        if total == 0:
            return {}
        return {t: freq / total for t, freq in type_frequencies.items()}

    def resolve(self, entity: Entity, context: ResolverContext) -> str:
        """Resolve entity type using Bayesian inference. Returns type name."""
        if not self._prior:
            return entity.type

        # Get top-k candidate types by prior
        candidates = sorted(self._prior.items(), key=lambda x: -x[1])[: self._top_k]
        candidate_types = [t for t, _ in candidates]

        # If current type is valid and in candidates, may not need resolution
        if entity.type in self._prior and entity.type in candidate_types:
            # Still run evidence to potentially reassign
            pass

        # Compute posterior for each candidate
        posterior: dict[str, float] = {}
        for type_name in candidate_types:
            prior_p = self._prior.get(type_name, 1e-6)
            likelihood_exemplar = self._exemplar_likelihood(
                entity,
                type_name,
                context.entity_embedding,
            )
            likelihood_rels = self._relationship_likelihood(
                entity,
                type_name,
                context.relationships,
            )
            posterior[type_name] = prior_p * likelihood_exemplar * likelihood_rels

        # Normalize posterior
        total_p = sum(posterior.values())
        if total_p > 0:
            posterior = {t: p / total_p for t, p in posterior.items()}
        else:
            return entity.type

        # Check entropy
        entropy = self._entropy(posterior)
        best_type = max(posterior, key=lambda t: posterior[t])
        best_prob = posterior[best_type]

        if entropy < self._entropy_threshold:
            if best_type != entity.type:
                logger.debug(
                    "Bayesian resolve: '{}' {} -> {} (p={:.3f}, H={:.3f})",
                    entity.name,
                    entity.type,
                    best_type,
                    best_prob,
                    entropy,
                )
            return best_type
        else:
            # High entropy - fall back to highest posterior (no LLM escalation yet)
            if best_type != entity.type:
                logger.debug(
                    "Bayesian resolve (uncertain): '{}' {} -> {} (p={:.3f}, H={:.3f})",
                    entity.name,
                    entity.type,
                    best_type,
                    best_prob,
                    entropy,
                )
            return best_type

    def _exemplar_likelihood(
        self,
        entity: Entity,
        type_name: str,
        entity_embedding: list[float] | None,
    ) -> float:
        """Compute P(name|type) from exemplar similarity."""
        if self._index and self._index.is_built and entity_embedding:
            results = self._index.query(entity_embedding, top_k=self._top_k)
            for t, sim in results:
                if t == type_name:
                    # Shift similarity to positive likelihood range
                    return max(sim, 0.01) + 0.5
            return 0.5  # neutral if type not in results

        # Levenshtein fallback - no index or no embedding
        return 1.0  # uniform - no evidence

    def _relationship_likelihood(
        self,
        entity: Entity,
        type_name: str,
        relationships: list[Relationship],
    ) -> float:
        """Compute P(rels|type) from relationship context.

        Entities participating in relationships whose type name contains
        the candidate type name get a boost.
        """
        if not relationships:
            return 1.0

        type_lower = type_name.lower()
        entity_id = entity.id
        rel_score = 0.0
        rel_count = 0

        for rel in relationships:
            if rel.source == entity_id or rel.target == entity_id:
                rel_count += 1
                rel_type_lower = rel.type.lower().replace("_", "")
                # Simple heuristic: if relationship type contains type name
                if type_lower in rel_type_lower or rel_type_lower in type_lower:
                    rel_score += 1.0

        if rel_count == 0:
            return 1.0

        # Scale: more matching relationships = higher likelihood
        return 1.0 + (rel_score / rel_count)

    @staticmethod
    def _entropy(distribution: dict[str, float]) -> float:
        """Compute Shannon entropy of a probability distribution."""
        h = 0.0
        for p in distribution.values():
            if p > 0:
                h -= p * math.log2(p)
        return h
