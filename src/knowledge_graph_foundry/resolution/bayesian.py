"""Bayesian pairwise evidence model.

Odds-form posterior P(same_entity | evidence): a prior from name identity
multiplied by likelihood ratios for description similarity, embedding
cosine and chunk co-occurrence. The description LR is floored so a missing
description never fully vetoes; the embedding LR is neutral (1.0) when
either embedding is absent. Validated in v1 (cut cross-type duplicates
56 -> 39); heuristics may set the prior, never bypass the posterior.
"""

from __future__ import annotations

from typing import Optional

from knowledge_graph_foundry.models import Entity, ResolutionDecision, normalize_name
from knowledge_graph_foundry.resolution.similarity import (
    cosine_similarity,
    description_similarity,
    name_similarity,
)
from knowledge_graph_foundry.settings import ResolutionSettings


def name_prior(sim: float, cfg: ResolutionSettings) -> float:
    """Continuous prior from name similarity: fuzzy floor below 0.5, then a
    linear ramp to the identical prior at 1.0. Graded evidence, not a cutoff."""
    if sim >= 1.0:
        return cfg.name_prior_identical
    ramp = max(0.0, (sim - 0.5) / 0.5)
    return cfg.name_prior_fuzzy + (cfg.name_prior_identical - cfg.name_prior_fuzzy) * ramp


def evidence(
    left: Entity,
    right: Entity,
    cfg: ResolutionSettings,
    prior_override: Optional[float] = None,
) -> ResolutionDecision:
    """Score one candidate pair; the decision applies three-zone logic."""
    if prior_override is not None:
        prior = prior_override
    else:
        sim = name_similarity(normalize_name(left.name), normalize_name(right.name))
        prior = name_prior(sim, cfg)

    lr_desc = max(
        cfg.description_lr_floor, description_similarity(left.description, right.description) * 2.0
    )

    lr_emb = 1.0
    if left.embedding and right.embedding:
        lr_emb = max(0.2, cosine_similarity(left.embedding, right.embedding) * 2.0)

    shared = set(left.source_chunks) & set(right.source_chunks)
    lr_cooc = 1.5 if shared else 0.9

    prior_odds = prior / (1.0 - prior)
    posterior_odds = prior_odds * lr_desc * lr_emb * lr_cooc
    posterior = posterior_odds / (1.0 + posterior_odds)

    if posterior >= cfg.merge_threshold:
        decision = "merge"
    elif posterior >= cfg.defer_lower:
        decision = "defer"
    else:
        decision = "block"

    return ResolutionDecision(
        left_id=left.id,
        right_id=right.id,
        prior=prior,
        lr_description=lr_desc,
        lr_embedding=lr_emb,
        lr_cooccurrence=lr_cooc,
        posterior=posterior,
        decision=decision,
    )
