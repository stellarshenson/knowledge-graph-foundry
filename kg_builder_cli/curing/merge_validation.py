"""Post-LLM merge validation for type clustering.

Catches over-aggressive merges (e.g. Mode->Role, Gas->Accessory) that the LLM
proposes due to prompt pressure. Uses three lightweight metrics - no external
dependencies beyond stdlib + pydantic.
"""

from __future__ import annotations

from difflib import SequenceMatcher
import re

from loguru import logger
from pydantic import BaseModel

# Stop words for description coherence (common English, kept minimal)
_STOP_WORDS = frozenset(
    "a an the is are was were be been being have has had do does did "
    "will would shall should may might can could of in to for on with "
    "at by from as into through during before after above below between "
    "and or but not no nor so yet both either neither each every all "
    "any few more most other some such than too very it its this that "
    "these those".split()
)


class MergeValidation(BaseModel):
    """Validation result for a single proposed merge."""

    source_type: str
    target_type: str
    name_similarity: float
    description_coherence: float
    frequency_ratio: float
    confidence: float
    flagged: bool


class ClusteringValidationResult(BaseModel):
    """Aggregated validation of all proposed merges."""

    merge_validations: list[MergeValidation]
    flagged_count: int
    approved_mapping: dict[str, str]


def _split_pascal_case(name: str) -> set[str]:
    """Split PascalCase into lowercase word set."""
    words = re.findall(r"[A-Z][a-z]*|[a-z]+|[A-Z]+(?=[A-Z][a-z]|\b)", name)
    return {w.lower() for w in words if w}


def _name_similarity(a: str, b: str) -> float:
    """Combined Levenshtein ratio + Jaccard on PascalCase word sets.

    Returns average of SequenceMatcher ratio and word-set Jaccard.
    """
    seq_ratio = SequenceMatcher(None, a.lower(), b.lower()).ratio()

    words_a = _split_pascal_case(a)
    words_b = _split_pascal_case(b)
    if not words_a and not words_b:
        return seq_ratio
    intersection = words_a & words_b
    union = words_a | words_b
    jaccard = len(intersection) / len(union) if union else 0.0

    return (seq_ratio + jaccard) / 2.0


def _significant_words(text: str) -> set[str]:
    """Extract significant words from text, removing stop words."""
    words = re.findall(r"[a-z]+", text.lower())
    return {w for w in words if w not in _STOP_WORDS and len(w) > 2}


def _description_coherence(
    source_type: str,
    target_type: str,
    entity_descriptions: dict[str, list[str]],
) -> float:
    """Jaccard similarity on significant words from entity descriptions.

    Collects all descriptions for entities of each type, extracts significant
    words, and computes Jaccard overlap.
    """
    source_descs = entity_descriptions.get(source_type, [])
    target_descs = entity_descriptions.get(target_type, [])

    source_words: set[str] = set()
    for desc in source_descs:
        source_words |= _significant_words(desc)

    target_words: set[str] = set()
    for desc in target_descs:
        target_words |= _significant_words(desc)

    if not source_words and not target_words:
        return 0.5  # neutral when no descriptions available

    union = source_words | target_words
    if not union:
        return 0.5

    intersection = source_words & target_words
    return len(intersection) / len(union)


def _frequency_ratio(freq_a: int, freq_b: int) -> float:
    """Ratio of min/max frequency. Returns 1.0 for equal, 0.0 for infinite gap."""
    if freq_a == 0 and freq_b == 0:
        return 1.0
    max_f = max(freq_a, freq_b)
    min_f = min(freq_a, freq_b)
    return min_f / max_f if max_f > 0 else 0.0


def validate_type_clustering(
    mapping: dict[str, str],
    frequencies: dict[str, int],
    all_entities: list,
    threshold: float = 0.4,
    w_name: float = 0.55,
    w_desc: float = 0.35,
    w_freq: float = 0.10,
) -> ClusteringValidationResult:
    """Validate proposed type merges and revert low-confidence ones.

    Args:
        mapping: LLM-proposed type mapping (source -> canonical).
        frequencies: Entity type frequencies.
        all_entities: List of entity objects with .type and .description attrs.
        threshold: Minimum confidence to approve a merge.
        w_name: Weight for name similarity (default 0.55).
        w_desc: Weight for description coherence (default 0.35).
        w_freq: Weight for frequency ratio (default 0.10).

    Returns:
        ClusteringValidationResult with approved_mapping where flagged
        merges are reverted to identity (source maps to itself).
    """
    # Build description index: type -> list of descriptions
    entity_descriptions: dict[str, list[str]] = {}
    for entity in all_entities:
        t = getattr(entity, "type", None)
        desc = getattr(entity, "description", None)
        if t and desc:
            entity_descriptions.setdefault(t, []).append(desc)

    validations: list[MergeValidation] = []
    approved_mapping: dict[str, str] = {}
    flagged_count = 0

    for source, target in mapping.items():
        # Identity merges skip validation
        if source == target:
            approved_mapping[source] = target
            continue

        name_sim = _name_similarity(source, target)
        desc_coh = _description_coherence(source, target, entity_descriptions)
        freq_rat = _frequency_ratio(frequencies.get(source, 0), frequencies.get(target, 0))

        confidence = w_name * name_sim + w_desc * desc_coh + w_freq * freq_rat
        flagged = confidence < threshold

        validation = MergeValidation(
            source_type=source,
            target_type=target,
            name_similarity=round(name_sim, 3),
            description_coherence=round(desc_coh, 3),
            frequency_ratio=round(freq_rat, 3),
            confidence=round(confidence, 3),
            flagged=flagged,
        )
        validations.append(validation)

        if flagged:
            flagged_count += 1
            approved_mapping[source] = source  # revert to identity
            logger.warning(
                "[merge-validation] REVERTED {}->{}: confidence={:.3f} "
                "(name={:.3f}, desc={:.3f}, freq={:.3f})",
                source,
                target,
                confidence,
                name_sim,
                desc_coh,
                freq_rat,
            )
        else:
            approved_mapping[source] = target
            logger.debug(
                "[merge-validation] approved {}->{}: confidence={:.3f}",
                source,
                target,
                confidence,
            )

    if flagged_count > 0:
        logger.info(
            "[merge-validation] {} of {} merges reverted (below threshold {:.2f})",
            flagged_count,
            len(validations),
            threshold,
        )

    return ClusteringValidationResult(
        merge_validations=validations,
        flagged_count=flagged_count,
        approved_mapping=approved_mapping,
    )
