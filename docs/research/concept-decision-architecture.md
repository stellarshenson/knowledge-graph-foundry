# Decision Architecture: Two-Layer Adjudication, Calibration, and Safety

| | |
|---|---|
| **Raised** | 2026-03-17 |
| **Status** | Open |
| **Last Update** | 2026-03-17 |
| **Design Comments** | - |
| **Implementation Notes** | - |

## Two-Layer Decision Model

Entity resolution operates as a two-layer system: a statistical layer that produces calibrated merge probabilities, and a reasoning layer that adjudicates action under context. The LLM does not replace the probability model - it acts as a policy layer over it.

**Layer 1 - Statistical posterior**: From structured and unstructured evidence, compute a calibrated probability of same entity. This layer provides statistical regularity - consistent handling of the common cases where signals agree.

**Layer 2 - Reasoning adjudicator**: The LLM reads the candidate pair, extracted evidence, graph context, contradictions, source provenance, and the calibrated probability. It emits a control signal: merge, block, defer, or request more evidence. The LLM is not deciding from scratch - it is adjudicating on a well-characterized case.

The reasoning model operates as a conservative veto mechanism with an asymmetric action space. It can uphold a merge or block it, but it cannot force a merge when evidence is weak. The worst outcome is preventing merges that should have happened (false splits), which is the safer failure mode compared to false merges that contaminate the graph.

The LLM should see not just the final posterior but the per-channel contributions, disagreement score across channels, missingness pattern, provenance quality, and contradiction flags. The decision matrix: high posterior + low conflict -> merge; high posterior + high conflict -> block or defer; mid posterior + coherent channels -> merge candidate; mid posterior + fragmented evidence -> block; low posterior + any signal -> usually do not merge.

The statistical layer handles volume efficiently. The reasoning layer handles nuance that pure similarity models miss - name collisions, temporal contradictions, incompatible attributes, source distrust, graph topology anomalies. Neither layer alone is sufficient.

## Bayesian Decision Calibration

A hardcoded merge threshold (e.g. 0.6) is just another uncertain parameter. Bayesian decision calibration separates two distinct problems that must not be mixed:

**Probability calibration** asks whether a posterior score of 0.8 actually means 80% chance of same entity. Isotonic regression, Platt scaling, or beta calibration fix warped score distributions so probabilities mean what they claim.

**Decision calibration** asks where the action boundary should be given the cost of false merge versus false split. In entity resolution, false merges are typically far more damaging - a false merge poisons the graph and propagates corruption, while a false split merely leaves duplicates. The optimal threshold derives from costs and uncertainty: merge when probability exceeds the ratio of false-positive cost to total cost.

Three architectures in order of sophistication: (1) calibrate posterior scores externally, then derive threshold from expected loss - safest starting point; (2) hierarchical Bayesian thresholding where threshold varies by entity type, source system, ambiguity class with group-level partial pooling; (3) full Bayesian utility model with no explicit threshold, choosing the action with higher expected utility.

The starting threshold of 0.6 is a reasonable prior for a new graph. The threshold does not need to move much if the probability model keeps improving through calibration. The right question is not "what should the threshold be?" but "when is the model safe to trust without reasoning?"

## Contextual Adjudication Trigger

A hardcoded scalar threshold is too crude for a system operating across diverse entity types, source qualities, and graph regions. The replacement is a contextual trigger function that considers multiple features when deciding whether a candidate pair needs LLM reasoning.

Instead of a single test against a fixed value, the trigger becomes a learned probability that considers calibrated posterior, channel conflict, evidence sparsity, and entity type context. The "threshold" is no longer a number - it is a decision boundary in feature space.

Rather than a binary trigger, the model defines three zones: low probability zone (never merge, no adjudication needed), high probability zone with low conflict (merge automatically), and middle or high-conflict zone (adjudicate with LLM reasoning). This reduces LLM load by reserving reasoning for cases where it actually adds value.

Per-entity thresholds would be unstable without sufficient data. Hierarchical partial pooling is more appropriate - trigger parameters learned at group level (entity type, source system, ontology class) with individual pairs inheriting from their group. A new graph starts with prior parameters and updates group-level triggers as evidence accumulates.

The trigger decision is mostly a contextual bandit or cost-sensitive classification problem, not a full reinforcement learning problem. The action space is small and the reward signal is delayed but straightforward. Full RL introduces unnecessary complexity for this decision structure.

## Epistemic Loop Prevention

When a system learns from its own decisions rather than from reality, it converges to a confident hallucination machine. If the LLM decides the action, and the resulting action becomes the evidence used to calibrate the probability model, the system reinforces its own decisions: posterior model -> LLM action -> stored outcome -> calibration update -> new posterior. The "outcome" is not ground truth - it is just the consequence of the LLM's decision.

**Three ways to break the loop**:

1. **Freeze calibration signal**: Only update calibration from events that become externally verified - future contradictory evidence, downstream reconciliation, later document ingestion confirming identity, or deterministic attributes like identifiers
2. **Separate decision logs from truth logs**: LLM decisions are policy output. Truth signals come from independent observations only
3. **Treat LLM as policy prior, not label generator**: The statistical model never learns from LLM choices, only from observed contradictions or confirmations in the graph

Even with the one-way veto design, a subtle reverse loop can form. If blocked merges are treated as implicit evidence that entities are different, the system slowly becomes overly conservative and the graph fills with duplicates. Prevention: blocked merges must be classified as "unknown", not as negative labels. The three-state model (merge / no-merge / unknown) is essential.

**Core rule**: The system must never learn truth from its own decisions. Truth must come from delayed evidence in the world or the graph.
