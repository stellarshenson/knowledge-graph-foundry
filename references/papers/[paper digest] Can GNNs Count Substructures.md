**Can Graph Neural Networks Count Substructures? (2020, NeurIPS)**

The expressiveness ceiling for GNN pattern matching. The paper proves that message-passing GNNs (MPNNs), 2-Weisfeiler-Leman (2-WL) and 2-Invariant Graph Networks **cannot induced-subgraph-count any connected pattern of 3 or more nodes** - no triangles, no cycles, no paths as motifs - while they **can count star-shaped patterns**. Higher-order **k-WL / k-IGN can count** (at k-fold cost), and the proposed Local Relational Pooling counts substructures and stays competitive on molecular tasks.

**Key mechanism**
- Ties substructure counting to the Weisfeiler-Leman hierarchy: what a model can count = what its WL level can distinguish
- Negative result: MPNN/2-WL blind to any connected >=3-node induced subgraph; also negative results for finite-iteration k-WL
- Local Relational Pooling (LRP): aggregate over permutations of small local egonets to recover counting power

**Main findings**
- Star-shaped substructures (a center + leaves) ARE countable by plain MPNNs
- Every connected motif of >=3 nodes (triangle, path-of-3, cycle) is NOT
- Escaping the ceiling requires higher-order or subgraph-based architectures, which cost more

**Key takeaways**
- A vanilla GNN provably cannot detect the multi-node PATTERNS that define relational reasoning - pattern matching is not a capability you get for free from message passing
- The user's intuition that GNN pattern-matching "requires a different architecture" is a theorem, not a hunch
- Star-shaped patterns are the exception - hop-0 hub neighborhoods are within reach

**Relevance**
- KGF's 2wiki bridge/comparison questions are 2-hop PATH and two-star-join shapes; the path/join component is exactly what a plain GNN cannot count, so any KGF GNN-matcher must be a subgraph-GNN (ESAN) or use substructure features (GSN)
- Mitigating fact: 91% of KGF's recalled evidence is hop-0 (star-shaped around a seed) - the expressiveness gap bites only on the residual multi-hop / comparison slice, which is precisely the H592/H593 target class
- Sets the honest cost floor: expressiveness beyond stars = k-fold compute, on a graph where PPR already reaches the same shapes for free

**Tags**
- #Expressiveness #WeisfeilerLeman #SubstructureCounting #GNNTheory

**Source**
- Download: https://arxiv.org/pdf/2002.04025
- Local: [paper] Can GNNs Count Substructures, 2020.pdf
