# Resolution limit in community detection

**Authors**: Santo Fortunato, Marc Barthelemy

**arXiv link (source for re-download)**: https://arxiv.org/abs/physics/0607100

**Publication date**: 2006-07 (physics/0607100; v2 14 Jul 2006)

## Summary

- Modularity optimization cannot resolve modules smaller than a scale set by the network's total link count L - even when those modules are complete graphs joined by a single bridging edge
- The most-modular partition of any network has close to m* = sqrt(L) modules, each holding l = sqrt(L) - 1 internal links, so modularity carries an intrinsic scale of order sqrt(L) regardless of the network's actual community structure
- Two interconnected modules get merged by modularity optimization whenever each has fewer than l_min_R = sqrt(L)/2 internal links, and fuzzy (loosely bounded) modules can be merged even when each holds up to l_max_R = L/4 internal links
- A module found by modularity optimization with l_S internal links may itself be a fused pair of smaller communities whenever l_S < sqrt(2L) - the paper's headline resolution-limit threshold
- Worked ring-of-cliques example: n=30 cliques of size m=5 (K5) linked in a ring gives Q_single = 0.876 for the true one-clique-per-module partition versus Q_pairs = 0.888 for merged pairs of cliques - the higher-modularity partition is the wrong one
- On five real networks (yeast and E. coli transcriptional regulation, an electronic circuit, a social network, C. elegans neural network), simulated-annealing modularity peaks found 9-27 modules per network (Q_max 0.4022-0.7519), but re-optimizing modularity inside each module surfaced 15-76 submodules with lower total modularity (0.3613-0.6770) - confirming the peak-modularity partition was under-resolved in every case
- On Amazon.com's co-purchase network (409,687 nodes, 2,464,630 edges, 1,684 communities from prior greedy modularity optimization with a power-law size distribution of exponent 2), the authors estimate over 95% of detected modules fall below the sqrt(2L) limit, meaning nearly all of them warrant further splitting

The mechanism is a direct algebraic consequence of modularity's global normalization: because modularity compares each module's link fraction against a random-graph null model normalized by the whole network's link count L, whether a subgraph counts as "more modular when merged" depends on L itself, not on any local property of the subgraph - so modularity implicitly imposes a network-size-dependent minimum resolvable module size rather than a scale-free notion of community.

**Relevance to Knowledge Graph Foundry**: KGF's Leiden communities (used as provenance artifacts, NMI 0.614 with source docs) are built on modularity-family optimization, so this paper's sqrt(2L)-scale resolution limit is the theoretical reason small but genuine communities can get silently fused as the graph grows - directly bearing on R48's community segmentation/balancing work and on interpreting Leiden's NMI ceiling as partly a resolution-limit artifact rather than pure noise.
