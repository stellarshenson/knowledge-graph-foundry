# Ontology Lifecycle: Curing and Adaptive Resolution

| | |
|---|---|
| **Raised** | 2026-03-17 |
| **Status** | Implemented |
| **Last Update** | 2026-03-17 |
| **Design Comments** | - |
| **Implementation Notes** | - |

## Curing and Stabilization

Ontology curing is a phase-based stabilization mechanism that addresses ontology chaos during early extraction. Most knowledge graph builders take one of two approaches: a fixed ontology defined upfront, or a fully emergent ontology with uncontrolled drift. KGF introduces a third option - a stabilization phase driven by metrics and drift detection.

During the fluid phase the system discovers entity types freely from the corpus. As extraction progresses, statistical signals accumulate: type accumulation rate declines, entropy stabilizes, Chao1 coverage converges, and Jensen-Shannon divergence between consecutive documents drops below threshold. When these signals collectively indicate that the ontology has reached a natural plateau, the system enters curing - freezing the discovered types into a constrained schema for the remainder of ingestion.

The curing decision is not a simple threshold on a single metric. It represents a convergence judgment across multiple statistical indicators. The system can also re-cure if post-curing drift detection identifies sustained remap rates or missing type categories, creating a full lifecycle: fluid -> curing -> cured -> drift detection -> recuring -> cured.

Without curing, LLM extraction drifts across documents - the same real-world concept gets extracted as different types in different documents. With curing, the ontology stabilizes early enough to enforce consistency across the remaining corpus while remaining data-driven rather than manually prescribed. This is one of the most original elements of the architecture, uncommon in both commercial and research KG builders.

## Adaptive Resolution Guides

Resolution guides are heuristics that evolve from accumulated ambiguous cases during entity resolution. Instead of hardcoding type dominance rules or letting the LLM improvise every resolution decision from scratch, the system learns resolution patterns from evidence encountered during ingestion.

When the Bayesian resolver encounters ambiguous entity pairs - same name appearing as different types across documents - it records the outcome and the evidence that led to it. Over time, patterns emerge: certain type pairs consistently resolve in one direction (Component absorbs Accessory when co-occurring with HAS_COMPONENT relationships), while others represent genuine dual-typing (humidifier legitimately exists as both Component and Accessory depending on context).

These patterns are codified as resolution guide rules in the ontology buffer. The ontology buffer tracks cross-type encounter statistics. When a type pair accumulates enough encounters (threshold of 3+), the system can evolve a hierarchy entry - declaring one type as parent of another, or establishing that a specific pair represents legitimate dual-typing that should not be merged. These hierarchy entries then inform future Bayesian posteriors as prior information.

Resolution guides create institutional memory within the graph construction process. The system gets smarter about its own domain as it processes more documents, without requiring manual rule authoring or expensive LLM calls for every decision. This hybrid learning layer between rule-based and agentic reasoning is uncommon in current KG builder tools.
