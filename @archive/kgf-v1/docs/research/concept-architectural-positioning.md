# Architectural Positioning: Innovation Classification and Design Principles

| | |
|---|---|
| **Raised** | 2026-03-17 |
| **Status** | Open |
| **Last Update** | 2026-03-17 |
| **Design Comments** | - |
| **Implementation Notes** | - |

## Innovation Classification

KGF is architecturally innovative, not algorithmically groundbreaking. Every individual component - LLM extraction, ontology-guided resolution, hybrid lexical + embedding similarity, graph construction pipelines, agent escalation - exists somewhere in the current ecosystem. The innovation lies in how the pieces are combined and disciplined.

- Component innovation: low (individual techniques are known)
- System integration innovation: high (combination is uncommon)
- Operational design innovation: medium to high (lifecycle governance, observability)

KGF tries to solve three problems simultaneously that most tools address only individually: ontology drift (via curing/recuring lifecycle), ambiguous entity resolution (via Bayesian posterior with evidence accumulation), and operational observability of KG construction (via event architecture and FSM). Most tools solve only one of these.

**Comparison with existing systems**: Neo4j Graph Builder has strong UI but almost no adaptive ontology management. Diffbot has strong extraction models but fixed ontology. LlamaIndex/LangChain KG modules are agent-heavy with weak ontology discipline. Research systems like Graphusion and AGENTiGraph are sophisticated but rarely operationalized, lacking lifecycle governance.

Framing matters. Describing KGF as "a knowledge graph builder" invites comparison with simpler tools. Describing it as "an adaptive ontology stabilization and resolution system for LLM-generated knowledge graphs" positions the novelty correctly. Historical parallel: Docker did not invent containers, Kubernetes did not invent orchestration - they integrated known ideas into disciplined systems.

## Agent Escalation Boundaries

The architecture uses LLM agents only when deterministic logic cannot decide. This restraint distinguishes KGF from rigid deterministic pipelines that never reason and agent-first architectures that call an LLM for every operation.

The hot path - chunk extraction, basic deduplication, type enforcement, graph loading - runs through structured LLM calls or pure deterministic code. Agents are invoked only at specific decision points where evidence is genuinely ambiguous: cross-type entity resolution in the Bayesian gray zone, borderline curing decisions, or type resolution where Levenshtein similarity is inconclusive.

Agent calls are expensive in latency and tokens. By restricting them to decision boundaries, the system preserves throughput on the common path while accessing reasoning when it matters. Structured LLM calls with constrained response models produce reproducible outputs. Agent reasoning introduces non-determinism. By confining agents to boundaries, the system maintains largely deterministic behavior with controlled points of non-determinism that are logged and auditable.

## Design Signature

The architecture reads as the work of a data scientist who is also an engineer. Empirical feedback loops, probabilistic reasoning, measurement discipline, and evaluation rigor signal data science thinking. Architectural restraint, operational simplicity, and clear module boundaries signal engineering discipline. The blend of both is visible throughout: iterating through evidence rather than designing first and testing later, asking "what is the probability?" rather than combining similarity scores, and recognizing when benchmark measurement artifacts (judge context truncation) explain score gaps rather than pipeline deficiencies.
