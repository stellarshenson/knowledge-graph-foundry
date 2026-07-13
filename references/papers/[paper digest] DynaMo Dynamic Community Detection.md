# DynaMo: Dynamic Community Detection by Incrementally Maximizing Modularity

**Authors**: Di Zhuang, J. Morris Chang, Mingchen Li (Department of Electrical Engineering, University of South Florida)

**arXiv link (source for re-download)**: https://arxiv.org/abs/1709.08350

**Publication date**: 2017-09-25 (first arXiv version)

## Summary

- DynaMo obtains **2.6%, 2.2%, 4.3%, 2.1%, 1.1% and 2.2%** higher modularity than the runner-up dynamic baseline (Batch), averaged over all time points, on Cit-HepPh, Cit-HepTh, DBLP, Facebook, Flickr and YouTube respectively
- Against Louvain (the static reference run from scratch on every snapshot), DynaMo loses only **0.06% to 0.7%** modularity on average across the six real-world networks - near-identical quality without full recomputation
- On 10,000 synthetic RDyn networks, DynaMo beats the runner-up dynamic algorithm (QCA) on NMI by **69.1%, 66.4% and 70.3%** on average as the number of vertices, events per time point, and time points respectively increase (two-sample t-test, 95% CI)
- DynaMo is **2 to 5 times faster than Louvain** (by average) on the same snapshot series, and beats Batch by up to **7x** and QCA by up to **5x** on individual networks, while running slower than the lighter-weight GreMod baseline on most datasets
- Best-case time complexity is **O(|ΔE| + |E|*)** and worst-case **O(|ΔE| · |E|/|V|)**, where |E|* ≪ |E| is the edge count surviving into the algorithm's second phase - versus O(|E|) for Louvain recomputed from scratch each snapshot
- Evaluated on 6 real-world dynamic networks (Cit-HepPh, Cit-HepTh, DBLP, Facebook, Flickr, YouTube; up to 3.16M vertices / 7.2M edges) plus 10,000 RDyn-generated synthetic networks with known ground truth

**Key mechanism**
- Three-phase loop per network snapshot: Initialization → Adaptive Modularity Maximization → Refinement, applied only to the vertex/edge delta (ΔV, ΔE) between consecutive snapshots rather than the whole graph
- Six change-event types are handled with dedicated, theoretically-justified local operations: intra-community edge addition/weight increase, inter-community edge addition/weight increase, edge/weight removal in either direction, and vertex addition/deletion - each triggers a bounded modularity-gain check (splitting, merging, or reassigning the smallest affected unit) instead of a global re-run
- Refinement pass periodically re-examines communities for further split/merge gains once the incremental updates converge, closing the gap to a from-scratch Louvain run
- The approach targets the same modularity-maximization objective as Louvain but restricts recomputation to the "blast radius" of each change, giving Louvain-level output quality at a fraction of the cost

**Relevance to Knowledge Graph Foundry**: KGF's Leiden communities are currently a static, provenance-only artifact recomputed after ingest; DynaMo's incremental-update model - process only the entities/edges touched by a batch, not the whole graph - is a direct blueprint for making community structure (and the H382 context-escalation gate that consumes it) update online as documents land, instead of requiring a full re-cluster each round.

**Tags**: #DynaMo #DynamicCommunityDetection #Modularity #IncrementalGraphUpdate #Louvain
