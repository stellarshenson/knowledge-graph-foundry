# Limits of modularity maximization in community detection

**Authors**: Andrea Lancichinetti, Santo Fortunato

**arXiv link (source for re-download)**: https://arxiv.org/abs/1107.1155

**Publication date**: arXiv v2, 2012-02-12 (original submission 2011, arXiv ID 1107.1155)

## Summary

- Fraction of misclassified vertices never drops below 10% for any value of the resolution parameter λ, tested on LFR benchmark graphs of 10,000 and 50,000 vertices with well-separated clusters (mixing parameter µ = 0.1 and 0.3)
- For a three-cluster test case (two cliques of size nC = 13 plus a random subgraph of size nS, average degree ⟨k⟩S = 100), no λ can eliminate both merge and split biases once nS exceeds roughly 230 vertices
- Q2 ≈ 0.17 for a random subgraph where all vertices have degree k = 20 (giving optimal-cut fraction v ≈ 0.33 × MS); for k = 10, v ≈ 0.25 × MS - random subgraphs already look partly clusterable to modularity before any real structure exists
- Infomap detects the planted partition correctly across the full range of mixing parameter µ tested, while all multiresolution modularity variants (Reichardt-Bornholdt, Arenas-Fernandez-Gomez, Traag et al.'s Constant Potts Model) fail once cluster sizes span more than one order of magnitude, even at low µ
- Derives closed-form thresholds λ1 (above which random subgraphs get split) and λ2 (below which any two clusters get merged, even cliques joined by a single edge) and shows λ1 < λ2 is a common regime - i.e. no resolution value avoids both biases simultaneously
- Two opposite failure modes coexist rather than trade off cleanly: low resolution merges small clusters into larger ones, high resolution shards large clusters into fragments, and because both effects operate at once the true partition cannot be recovered by simply re-splitting or re-merging modularity's output

**Key mechanism**: The resolution parameter λ in generalized modularity Qλ trades off internal edge density against a null-model penalty term; the paper derives that the λ range which avoids merging is bounded above by λ1 = 2αSM/MS and the range avoiding splitting is bounded below by λ2 = 2M/(ξC+2)^2, and shows analytically that whenever real networks have heterogeneous (power-law) cluster size distributions, λ1 < λ2 for many cluster pairs simultaneously - so a single global λ cannot satisfy every pair's constraint at once. This is framed as a structural property of any method that optimizes a single global quality function over the whole graph, not a quirk of modularity specifically.

**Relevance to Knowledge Graph Foundry**: KGF's Leiden community detection (R48, NMI 0.614 with source docs) is a global-optimization clustering method in the same family the paper indicts - this result is direct evidence that a single resolution parameter cannot simultaneously avoid over-merging small entity clusters and over-splitting large ones when community sizes are heterogeneous (the expected regime for an entity graph), reinforcing that Leiden communities should stay scoped as provenance/context-segmentation artifacts rather than a ground-truth clustering to optimize resolution against.
