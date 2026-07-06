**Can Persistent Homology provide an efficient alternative for Evaluation of Knowledge Graph Completion Methods? (2023)**

Ranking-based KG-completion evaluation is quadratic and slow. This paper builds a filtration over the scored KG and computes persistent homology to produce "Knowledge Persistence", a topological fingerprint compared as a persistence diagram instead of scoring every triple. It correlates highly with ranking metrics while cutting evaluation from **up to 18 hours to 27 seconds** (~**99.96%** reduction).

**Key mechanism**
- Build a filtration over the scored KG as a threshold sweeps
- Compute persistent homology: H0 (components/merges) and H1 (loops)
- Produce "Knowledge Persistence", a topological fingerprint, and compare persistence diagrams instead of scoring every triple

**Main findings**
- KP is highly correlated with ranking metrics (Hits@N, MR, MRR)
- Evaluation drops from up to 18 hours to 27 seconds (~99.96% reduction)

**Key takeaways**
- Persistent homology is depth-agnostic and cheap
- Betti curves give a global quality scalar per snapshot
- A fingerprint substitutes for exhaustive triple scoring

**Relevance**
- Persistent homology is depth-agnostic and fits our shallow graph as a global quality/drift scalar
- False SAME_AS closures over-merge nodes, collapsing H0 (swelling the giant component) and injecting spurious H1 cycles; Betti curves per ingest snapshot give an early-warning over-merge/drift monitor across the ontology-freeze boundary

**Tags**
- #PersistentHomology #KGEvaluation #TopologicalDataAnalysis

**Source**
- Download: https://arxiv.org/pdf/2301.12929
- Local: [paper] knowledge persistence kg evaluation, 2023.pdf
