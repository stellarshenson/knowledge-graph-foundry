# From Louvain to Leiden: Guaranteeing Well-Connected Communities

**Authors**: V.A. Traag, L. Waltman, N.J. van Eck

**arXiv link (source for re-download)**: https://arxiv.org/abs/1810.08473

**Publication date**: 2018-10-19 (first arXiv version); this text dated 2019-10-31

## Summary

- Up to 25% of communities found by the Louvain algorithm are badly connected and up to 16% are fully disconnected internally, worst on the Amazon network (23% badly connected in the first iteration, rising to 25% after four iterations) and the DBLP network (16% disconnected after four iterations)
- Leiden is up to 20 times faster than Louvain on empirical networks, and on the hardest synthetic benchmark (n=10^7, mu=0.9) Louvain needs almost 2.5 days while Leiden finishes in fewer than 10 minutes
- On six empirical networks (DBLP, Amazon, IMDB, Live Journal, Web of Science, Web UK 2005), first-iteration Leiden is 2-20x faster than Louvain: only ~1.6x on Amazon/IMDB but more than 7x on Live Journal, more than 11x on Web of Science, and more than 20x on Web UK
- Key mechanism: three phases per level instead of Louvain's two - (1) fast local moving of nodes using a work queue that only re-visits nodes whose neighbourhood changed (not all nodes every pass), (2) a refinement phase that starts from a singleton partition and randomly merges nodes only within their phase-1 community and only if both sides are well connected to it, and (3) aggregation built on the refined partition while seeding the next level's node communities from the coarser phase-1 partition
- The refinement phase is what gives the connectivity guarantee: because sub-communities are carved out and only merged when locally well-connected, every community the algorithm can return is provably internally connected - Louvain has no such guarantee and can silently produce disconnected "communities" that get worse as iterations proceed, even as modularity keeps increasing
- Randomised (not greedy) merging in refinement, controlled by a parameter theta, is proven to still be able to reach the optimal partition (Appendix C1) while greedy merging in the same restricted move set provably cannot always reach it (Appendix C2)
- When iterated, the Leiden algorithm converges to a partition in which all subsets of all communities are locally optimally assigned, a stronger guarantee than Louvain's simple local optimality of individual nodes

**Relevance to Knowledge Graph Foundry**: KGF's Leiden communities are provenance/context artifacts (NMI 0.614 with source docs) feeding the H382 context-escalation gate and the R48 community segmentation/balancing round; this paper is the primitive-algorithm reference for that exact clustering step and its connectivity guarantee is directly load-bearing for R48's balance hypotheses - a badly connected or disconnected Louvain-style community would corrupt the segmentation signal Leiden is meant to supply.
