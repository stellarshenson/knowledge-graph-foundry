**A Fast and Efficient Incremental Approach toward Dynamic Community Detection, Zarayeneh, Kalyanaraman, arXiv:1904.08553, 2019**

A pruning technique for incremental (modularity-based) community detection on growing graphs: instead of rerunning Louvain/SLM from scratch or re-evaluating every vertex after a batch of edge insertions, **Δ-screening** examines only the newly added edges and provably selects the small subset of vertices whose community assignment could actually change, feeding that reduced set into the existing multi-level clustering loop.

**Summary**
- **3x speedup**: on a real-world network with 63M temporal edges over 12 time steps, the Δ-screening implementation completed in 1056 seconds versus the incremental baseline
- **5x speedup** in individual time steps on the sx-stackoverflow dataset (e.g. time step t10, where edges grew from 55,158,947 to 60,714,297 and most new edges were intra-community)
- **Rt set size** (fraction of vertices re-evaluated per iteration) ranged under 10% in some time steps for real-world inputs versus up to 100% for synthetic inputs
- On Arxiv HEP-TH the Rt-size fraction varied approximately 50%-90%; savings were much larger and more consistent on sx-stackoverflow
- Tested on synthetic MIT Graph Challenge streams (50K and 5M vertex variants, up to ~214M cumulative edges) and two SNAP real-world networks: Arxiv HEP-TH (27,770 vertices, 352,807 edges, 11 time steps) and sx-stackoverflow (2,601,977 vertices, 63,497,050 edges, 2-28 time steps)
- Both baseline and Δ-screening implementations outperformed static from-scratch recomputation by more than two orders of magnitude in some cases
- Modularity quality of the Δ-screening version was reported as almost identical to the full baseline despite evaluating far fewer vertices per iteration
- A secondary experiment sweeping temporal bin count (2 to 28 steps) on sx-stackoverflow found a plateau region (4-16 time steps) where % runtime savings stayed steady, with modularity declining gradually until ~16 steps and then dropping faster - proposed as a way to pick an appropriate temporal resolution for a dynamic graph

**Key mechanism**
- Given a batch of newly added edges Δt at time step t, sort them by source vertex and walk each edge (i, j) to classify candidate vertices into three provable categories: the edge endpoints themselves, neighbors of an endpoint that already sit in a community adjacent to the change, and (via a proof in the appendix) vertices with no incentive to migrate that can be safely skipped
- Only the resulting Rt subset of vertices is re-evaluated by the standard local-greedy modularity-gain step (ΔQ_i→C(j)) inside Louvain or SLM; all other vertices retain the community assignment carried over from the previous time step
- The technique is graph-structure-only (no re-clustering, no embedding, no LLM); it plugs into any modularity-optimizing multi-level algorithm as a pre-filter on which vertices enter the iterative loop

**Relevance to Knowledge Graph Foundry**: KGF's Leiden communities are recomputed globally at each ingest/curing pass; Δ-screening is a directly transferable, cheap deterministic filter - after a document batch lands, walk only the new/changed entity-relationship edges to identify the provably-affected vertex subset, and re-run Leiden's local move phase on just that subset instead of the whole graph, which would cut the cost of keeping community-derived provenance (and the R48 segmentation/balancing signals feeding the H382 context-escalation gate) fresh as the corpus grows incrementally rather than via periodic full recomputation.

**Tags**: #IncrementalCommunityDetection #DeltaScreening #DynamicGraphs #Louvain #Modularity

**Source**: https://arxiv.org/abs/1904.08553. Local: [paper] Delta-Screening Incremental Community Detection, 2019.pdf
