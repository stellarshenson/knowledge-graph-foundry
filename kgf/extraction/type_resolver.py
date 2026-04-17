"""Bayesian type resolver for post-extraction type assignment."""

from __future__ import annotations

from dataclasses import dataclass, field
import math
from typing import TYPE_CHECKING

from loguru import logger

from kgf.extraction.exemplar_index import ExemplarIndex
from kgf.types.config import LLMConfig, OntologyBufferConfig
from kgf.types.extraction import Entity, Relationship
from kgf.types.ontology import TypeExemplar

if TYPE_CHECKING:
    from kgf.curing.observation import ObservationCollector


@dataclass
class ResolverContext:
    """Context for resolving a single entity's type."""

    relationships: list[Relationship] = field(default_factory=list)
    chunk_entities: list[Entity] = field(default_factory=list)
    entity_embedding: list[float] | None = None


class TypeResolutionResult:
    """Result from LLM-based type resolution."""

    def __init__(self, chosen_type: str, reasoning: str = ""):
        self.chosen_type = chosen_type
        self.reasoning = reasoning


class BayesianTypeResolver:
    """Resolve entity types using Bayesian inference over multiple evidence signals.

    Prior: normalized type frequencies from the ontology buffer.
    Likelihoods: exemplar similarity, relationship context, co-occurrence, description semantics.
    """

    def __init__(
        self,
        config: OntologyBufferConfig,
        type_frequencies: dict[str, int],
        exemplar_index: ExemplarIndex | None = None,
        type_exemplars: dict[str, tuple[TypeExemplar, ...]] | None = None,
        llm_config: LLMConfig | None = None,
        llm_escalation: bool = False,
        neo4j_config=None,
        collector: "ObservationCollector | None" = None,
        calibrator: object | None = None,
        type_metrics: dict[str, dict[str, float]] | None = None,
        adaptive_state: object | None = None,
    ):
        self._top_k = config.type_resolution_top_k
        self._entropy_threshold = config.type_resolution_entropy_threshold
        self._prior = self._build_prior(type_frequencies)
        self._index = exemplar_index
        self._type_exemplars = type_exemplars or {}
        self._llm_config = llm_config
        self._llm_escalation = llm_escalation
        self._neo4j_config = neo4j_config
        self._collector = collector
        self._calibrator = calibrator
        self._type_metrics = type_metrics
        self._adaptive_state = adaptive_state
        if type_metrics is not None:
            self._prior = self._build_multi_channel_prior(type_frequencies, type_metrics)

    def _build_prior(self, type_frequencies: dict[str, int]) -> dict[str, float]:
        """Build prior P(type) from normalized type frequencies."""
        total = sum(type_frequencies.values())
        if total == 0:
            return {}
        return {t: freq / total for t, freq in type_frequencies.items()}

    def _build_multi_channel_prior(
        self,
        type_frequencies: dict[str, int],
        type_metrics: dict[str, dict[str, float]],
        weights: dict[str, float] | None = None,
    ) -> dict[str, float]:
        """Build prior P(type) from weighted combination of type metrics.

        Each metric is normalized to [0, 1] across types (min-max scaling).
        Metrics with negative direction are inverted (1 - normalized).
        NaN metrics contribute 0 (neutral).
        Weights default to uniform if not provided.
        """
        if not type_metrics:
            return self._build_prior(type_frequencies)

        # Metrics where higher = worse (need inversion)
        _NEGATIVE_DIRECTION = {
            "freq_cv",
            "top3_concentration",
            "emb_centroid_dist",
            "discovery_order",
            "cross_type_rate",
            "hist_remap_rate",
            "cross_run_freq_delta",
        }

        # Collect all metric keys across types
        all_keys: set[str] = set()
        for metrics in type_metrics.values():
            all_keys.update(metrics.keys())

        if not all_keys:
            return self._build_prior(type_frequencies)

        # Min-max normalize each metric across types
        normalized: dict[str, dict[str, float]] = {t: {} for t in type_metrics}
        for key in all_keys:
            values = []
            for t in type_metrics:
                v = type_metrics[t].get(key, float("nan"))
                if not math.isnan(v):
                    values.append(v)

            if not values or (max(values) == min(values)):
                # Constant or all-nan -> neutral 0.5
                for t in type_metrics:
                    normalized[t][key] = 0.5
                continue

            vmin, vmax = min(values), max(values)
            for t in type_metrics:
                v = type_metrics[t].get(key, float("nan"))
                if math.isnan(v):
                    normalized[t][key] = 0.0  # nan contributes nothing
                else:
                    norm_v = (v - vmin) / (vmax - vmin)
                    if key in _NEGATIVE_DIRECTION:
                        norm_v = 1.0 - norm_v
                    normalized[t][key] = norm_v

        # Apply weights (uniform if not provided)
        available_keys = list(all_keys)
        if weights is None:
            w = {k: 1.0 / len(available_keys) for k in available_keys}
        else:
            w = weights

        # Compute weighted sum per type
        raw_scores: dict[str, float] = {}
        for t in type_metrics:
            score = 0.0
            for key in available_keys:
                score += w.get(key, 0.0) * normalized[t].get(key, 0.0)
            raw_scores[t] = score

        # Normalize to probability distribution
        total = sum(raw_scores.values())
        if total <= 0:
            return self._build_prior(type_frequencies)

        prior = {t: s / total for t, s in raw_scores.items()}
        logger.debug(
            "multi-channel prior: {} types, {} metrics",
            len(prior),
            len(available_keys),
        )
        return prior

    def resolve(self, entity: Entity, context: ResolverContext) -> str:
        """Resolve entity type using Bayesian inference. Returns type name."""
        if not self._prior:
            return entity.type

        # Use adaptive priors if available, otherwise frozen prior
        active_prior = self._prior
        if self._adaptive_state is not None and hasattr(
            self._adaptive_state, "get_adjusted_priors"
        ):
            adjusted = self._adaptive_state.get_adjusted_priors()
            if adjusted:
                active_prior = adjusted

        # Get top-k candidate types by prior
        candidates = sorted(active_prior.items(), key=lambda x: -x[1])[: self._top_k]
        candidate_types = [t for t, _ in candidates]

        # Compute posterior for each candidate
        posterior: dict[str, float] = {}
        for type_name in candidate_types:
            prior_p = active_prior.get(type_name, 1e-6)
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
            likelihood_cooccur = self._cooccurrence_likelihood(
                type_name,
                context.chunk_entities,
            )
            likelihood_desc = self._description_likelihood(
                entity,
                type_name,
            )
            posterior[type_name] = (
                prior_p
                * likelihood_exemplar
                * likelihood_rels
                * likelihood_cooccur
                * likelihood_desc
            )

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

        # Audit log: prior, posteriors, entropy for diagnostic tracing
        prior_str = " ".join(f"{t}={active_prior.get(t, 0):.3f}" for t in candidate_types)
        post_str = " ".join(f"{t}={posterior.get(t, 0):.3f}" for t in candidate_types)
        logger.debug(
            "Bayesian audit: {} | prior={{{}}} | posteriors={{{}}} | entropy={:.3f} | assigned={}",
            entity.name,
            prior_str,
            post_str,
            entropy,
            best_type,
        )

        # Apply calibration to best probability if calibrator available
        if self._calibrator is not None and hasattr(self._calibrator, "calibrate"):
            best_prob = self._calibrator.calibrate(best_prob)

        escalated = False
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
            resolved_type = best_type
        else:
            # High entropy - LLM escalation or argmax fallback
            if self._llm_escalation and self._llm_config:
                resolved_type = self._llm_resolve(entity, posterior, candidate_types)
                escalated = True
                if resolved_type != entity.type:
                    logger.debug(
                        "Bayesian resolve (LLM): '{}' {} -> {} (H={:.3f})",
                        entity.name,
                        entity.type,
                        resolved_type,
                        entropy,
                    )
            else:
                if best_type != entity.type:
                    logger.debug(
                        "Bayesian resolve (uncertain): '{}' {} -> {} (p={:.3f}, H={:.3f})",
                        entity.name,
                        entity.type,
                        best_type,
                        best_prob,
                        entropy,
                    )
                resolved_type = best_type

        # Record observation for calibration
        if self._collector is not None:
            from kgf.curing.observation import TypeAssignmentObservation

            self._collector.record_type_assignment(
                TypeAssignmentObservation(
                    entity_name=entity.name,
                    type_before=entity.type,
                    type_after=resolved_type,
                    posterior=dict(posterior),
                    entropy=entropy,
                    was_remapped=resolved_type != entity.type,
                    escalated_to_llm=escalated,
                    doc_index=0,
                )
            )

        return resolved_type

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

    def _cooccurrence_likelihood(
        self,
        type_name: str,
        chunk_entities: list[Entity],
    ) -> float:
        """Compute P(co_entities|type) from chunk co-occurrence.

        Entities co-occurring in the same chunk as known instances of a
        candidate type are more likely to be that type. Returns range [1.0, 2.0].
        """
        if not chunk_entities:
            return 1.0

        total = len(chunk_entities)
        matching = sum(1 for e in chunk_entities if e.type == type_name)
        return 1.0 + (matching / total)

    def _description_likelihood(
        self,
        entity: Entity,
        type_name: str,
    ) -> float:
        """Compute P(description|type) from keyword overlap with type exemplar descriptions.

        Bag-of-words intersection between entity description and all exemplar
        descriptions for the candidate type. Returns range [1.0, 2.0].
        """
        if not entity.description:
            return 1.0

        exemplars = self._type_exemplars.get(type_name, ())
        if not exemplars:
            return 1.0

        stop = {
            "a",
            "an",
            "the",
            "is",
            "are",
            "of",
            "for",
            "in",
            "to",
            "and",
            "or",
            "with",
            "that",
            "this",
        }
        entity_words = {
            w for w in entity.description.lower().split() if w not in stop and len(w) > 2
        }
        if not entity_words:
            return 1.0

        max_overlap = 0.0
        for ex in exemplars:
            if not ex.description:
                continue
            ex_words = {w for w in ex.description.lower().split() if w not in stop and len(w) > 2}
            if not ex_words:
                continue
            intersection = entity_words & ex_words
            # Normalize by smaller set size to avoid penalizing short descriptions
            overlap = len(intersection) / min(len(entity_words), len(ex_words))
            if overlap > max_overlap:
                max_overlap = overlap

        return 1.0 + max_overlap

    def _llm_resolve(
        self,
        entity: Entity,
        posterior: dict[str, float],
        candidate_types: list[str],
    ) -> str:
        """Use LLM to resolve ambiguous type assignment.

        Two-phase: if top-2 posterior gap < 0.15, entity has a description,
        and neo4j_config is available, queries graph for similar entities
        before the final LLM call. Falls back to argmax on any exception.
        """
        try:
            import time

            import instructor
            import litellm

            from kgf.events import signals as evt_signals
            from kgf.events import types as etypes
            from kgf.extraction.extract import extract_usage
            from kgf.extraction.unstructured import (
                _configure_aws_env,
                _litellm_model_id,
            )

            _configure_aws_env(self._llm_config)
            model_id = _litellm_model_id(self._llm_config)
            client = instructor.from_litellm(litellm.completion)

            # Build prompt with entity info and posterior
            posterior_str = ", ".join(
                f"{t}: {p:.3f}" for t, p in sorted(posterior.items(), key=lambda x: -x[1])
            )
            exemplar_str = ""
            for t in candidate_types:
                exs = self._type_exemplars.get(t, ())
                if exs:
                    names = [e.name for e in exs[:3]]
                    exemplar_str += f"\n  {t} examples: {', '.join(names)}"

            prompt = (
                f"An entity '{entity.name}' (description: '{entity.description}') "
                f"has ambiguous type assignment. The posterior probabilities are: {posterior_str}. "
                f"Type exemplars:{exemplar_str}\n\n"
                f"Which type best fits this entity? Respond with ONLY the type name, "
                f"choosing from: {', '.join(candidate_types)}"
            )

            # Graph query enrichment: two-phase when genuinely ambiguous
            sorted_probs = sorted(posterior.values(), reverse=True)
            top2_gap = sorted_probs[0] - sorted_probs[1] if len(sorted_probs) >= 2 else 1.0
            if top2_gap < 0.15 and entity.description and self._neo4j_config is not None:
                from kgf.curing.graph_query import GraphQueryRequest, query_graph

                request = GraphQueryRequest(
                    query_type="entity_search",
                    filter_name=entity.name,
                )
                try:
                    query_result = query_graph(request, self._neo4j_config)
                    if query_result.records:
                        graph_context = "\n".join(
                            f"  - {r['name']} (type: {r['type']})"
                            for r in query_result.records[:5]
                        )
                        prompt += (
                            f"\n\n**Existing graph entities matching '{entity.name}'**:\n"
                            f"{graph_context}"
                        )
                        logger.debug(
                            "LLM escalation enriched with {} graph matches for '{}'",
                            len(query_result.records),
                            entity.name,
                        )
                except Exception:
                    logger.debug("Graph query failed during LLM escalation for '{}'", entity.name)

            from pydantic import BaseModel as _BM

            class _TypeChoice(_BM):
                chosen_type: str
                reasoning: str = ""

            evt_signals.llm_call_started.send(
                evt_signals.llm_call_started,
                event=etypes.LLMCallStarted(
                    call_type="type_resolver_escalation",
                    model=model_id,
                    context={"entity_name": entity.name},
                ),
            )
            t0 = time.monotonic()

            result = client.chat.completions.create(
                model=model_id,
                response_model=_TypeChoice,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
                max_retries=1,
            )

            duration_ms = int((time.monotonic() - t0) * 1000)
            usage = extract_usage(result)
            evt_signals.llm_call_completed.send(
                evt_signals.llm_call_completed,
                event=etypes.LLMCallCompleted(
                    call_type="type_resolver_escalation",
                    model=model_id,
                    duration_ms=duration_ms,
                    token_count=usage["total_tokens"],
                    prompt_tokens=usage["prompt_tokens"],
                    completion_tokens=usage["completion_tokens"],
                ),
            )

            if result.chosen_type in candidate_types:
                return result.chosen_type
            # LLM returned invalid type, fall back to argmax
            logger.warning(
                "LLM escalation returned invalid type '{}', using argmax",
                result.chosen_type,
            )

        except Exception:
            logger.warning("LLM escalation failed for '{}', using argmax", entity.name)

        return max(posterior, key=lambda t: posterior[t])

    @staticmethod
    def _entropy(distribution: dict[str, float]) -> float:
        """Compute Shannon entropy of a probability distribution."""
        h = 0.0
        for p in distribution.values():
            if p > 0:
                h -= p * math.log2(p)
        return h
