"""Pydantic event payload models for the KGF pipeline event system.

~50 event types across 10 categories. Passed as event= kwarg to signal.send().
"""

from __future__ import annotations

from pydantic import BaseModel

# ── Pipeline Phase (3) ──────────────────────────────────────────────


class IngestionStarted(BaseModel):
    files: list[str]
    mode: str
    model: str


class PhaseTransition(BaseModel):
    from_phase: str
    to_phase: str
    trigger: str
    doc_index: int


class IngestionCompleted(BaseModel):
    total_docs: int
    total_entities: int
    total_rels: int


# ── Extraction (4) ──────────────────────────────────────────────────


class DocumentExtractionStarted(BaseModel):
    document_source: str
    doc_index: int
    total_docs: int
    chunk_count: int
    phase: str


class DocumentExtractionCompleted(BaseModel):
    document_source: str
    doc_index: int
    total_docs: int
    entity_count: int
    rel_count: int
    remap_count: int
    phase: str


class EntityResolutionCompleted(BaseModel):
    document_source: str
    entities_before: int
    entities_after: int
    id_map: dict[str, str]
    cross_type_stats: list[dict]


class TypeEnforcementApplied(BaseModel):
    document_source: str
    remap_count: int
    method: str


# ── Resolution Decisions (4) ───────────────────────────────────────


class CrossTypeDecision(BaseModel):
    entity_name: str
    type_a: str
    type_b: str
    prior: float
    posterior: float
    action: str
    lr_desc: float
    lr_emb: float
    lr_cooc: float
    has_hierarchy: bool
    sibling: bool
    doc_index: int


class CrossTypePairDeferred(BaseModel):
    entity_name: str
    type_a: str
    type_b: str
    posterior: float
    ambiguous_lower: float
    merge_threshold: float
    doc_index: int


class DeferredEvidenceUpdated(BaseModel):
    entity_name: str
    type_a: str
    type_b: str
    shared_chunks: int
    topology_jaccard: float
    posteriors_count: int
    desc_similarity: float


class DeferredResolutionCompleted(BaseModel):
    pairs_resolved: int
    merges: int
    blocks: int
    llm_escalations: int


# ── Ontology Evolution (6) ──────────────────────────────────────────


class OntologySignalsAccumulated(BaseModel):
    new_entity_types: int
    new_rel_types: int
    total_entity_types: int
    total_rel_types: int


class HierarchyPairQualifying(BaseModel):
    type_a: str
    type_b: str
    encounters: int
    threshold: int


class HierarchyEvolved(BaseModel):
    parent_name: str
    children: list[str]
    is_new: bool


class GuideRuleGenerated(BaseModel):
    entity_name: str
    dominant_type: str
    other_type: str
    dominance: float
    encounters: int


class OntologyEvolved(BaseModel):
    hierarchy_changes: int
    guide_rules_added: int
    trigger: str


class OntologyFlushed(BaseModel):
    path: str
    entity_type_count: int
    rel_type_count: int
    has_guide: bool


# ── Stability Metrics (2) ──────────────────────────────────────────


class StabilityMetricsRecorded(BaseModel):
    doc_index: int
    entity_count: int
    type_count: int
    entropy_shannon: float
    entropy_shannon_delta: float
    kl_divergence: float
    js_divergence: float
    type_accumulation_rate: float
    gini_coefficient: float
    zipf_r_squared: float
    heaps_beta: float
    chao1_estimate: float
    chao1_coverage: float
    ace_estimate: float
    rolling_jsd_var: float
    rolling_entropy_var: float


class StabilitySnapshot(BaseModel):
    doc_index: int
    metrics_summary: dict


# ── Curing Detection (6) ───────────────────────────────────────────


class CuringCheckPerformed(BaseModel):
    method: str
    result: bool
    doc_index: int
    details: dict


class CuringConditionBlocked(BaseModel):
    method: str
    condition: str
    actual_value: float
    threshold: float
    doc_index: int


class CuringTriggered(BaseModel):
    trigger: str
    doc_index: int
    accumulated_docs: int
    type_count: int


class DriftDetected(BaseModel):
    remap_rate: float
    consecutive_docs: int
    action: str


class DriftCheckPassed(BaseModel):
    remap_rate: float
    threshold: float
    doc_index: int


class PatienceExceeded(BaseModel):
    docs_processed: int
    max_patience: int
    trigger: str


# ── LLM Invocations (3) ────────────────────────────────────────────


class LLMCallStarted(BaseModel):
    call_type: str
    model: str
    doc_index: int | None = None
    context: dict = {}


class LLMCallCompleted(BaseModel):
    call_type: str
    model: str
    duration_ms: int
    token_count: int | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    doc_index: int | None = None


class LLMCallFailed(BaseModel):
    call_type: str
    model: str
    error_type: str
    error_message: str
    doc_index: int | None = None


# ── Blocked/Skipped Decisions (5) ──────────────────────────────────


class MergeBlocked(BaseModel):
    entity_name: str
    type_a: str
    type_b: str
    posterior: float
    reason: str
    doc_index: int


class MergeValidationFailed(BaseModel):
    cluster_label: str
    entity_names: list[str]
    confidence: float
    threshold: float
    reason: str


class HierarchySkipped(BaseModel):
    type_a: str
    type_b: str
    encounters: int
    threshold: int
    reason: str


class GuideRuleSkipped(BaseModel):
    entity_name: str
    type_a: str
    type_b: str
    dominance: float
    encounters: int
    reason: str


class DeferredPairSkipped(BaseModel):
    entity_name: str
    type_a: str
    type_b: str
    final_posterior: float
    reason: str


# ── Buffer Mutations (4) ───────────────────────────────────────────


class BufferTypesPruned(BaseModel):
    pruned_entity_types: list[str]
    pruned_rel_types: list[str]
    remaining_entity_types: int
    remaining_rel_types: int


class BufferExemplarsUpdated(BaseModel):
    entity_type: str
    exemplar_count: int


class BufferSnapshotTaken(BaseModel):
    path: str
    entity_type_count: int
    rel_type_count: int


class ConsolidationCompleted(BaseModel):
    entities_before: int
    entities_after: int
    rels_before: int
    rels_after: int
    deferred_resolved: int
    steps_completed: list[str]


# ── Loading (4) ────────────────────────────────────────────────────


class GraphLoadStarted(BaseModel):
    entity_count: int
    rel_count: int


class GraphLoadCompleted(BaseModel):
    entities_created: int
    entities_merged: int
    rels_created: int
    duration_ms: int


class GraphResolutionApplied(BaseModel):
    remapped_count: int


class GraphValidated(BaseModel):
    entity_count: int
    rel_count: int
    type_coverage: float
    orphan_count: int


# ── Calibration (1) ──────────────────────────────────────────────


class TypeMetricsComputed(BaseModel):
    type_count: int
    metric_count: int
    metrics_per_type: dict[str, dict[str, float]]
