**Incremental Multi-source Entity Resolution for Knowledge Graph Completion (2020) | Saeedi, Peukert, Rahm (University of Leipzig / ScaDS.AI)**

FAMER's incremental extension shows that naive one-at-a-time incremental entity resolution has "a strong dependency on the order in which new entities are added", and that a light-weight **n-depth reclustering (nDR) repair** step recovers batch-ER quality regardless of insertion order - direct empirical evidence for the premature-repair / carrier-order concern.

**Key mechanism**
- Batch ER in FAMER runs pairwise linking to build a similarity graph, then clusters it (CLIP algorithm); the incremental variant instead updates clusters entity-by-entity or set-by-set as new data arrives
- Max-both assignment: a new entity only joins its most-similar existing cluster if no other new entity from the same source is even more similar to that cluster, preventing greedy premature merges within one increment
- n-depth reclustering repairs prior wrong cluster decisions after the fact: it pulls the new entities plus their n-hop neighbor clusters in the existing clustered graph back into a local re-run of the batch clustering algorithm, bounding repair cost by the neighborhood depth n
- Reclustering depends on retained intra-cluster links, so it is not compatible with early cluster fusion (which discards those links for speed)

**Main findings**
- Simple incremental clustering without repair is order-dependent: early wrong decisions (often from lower-quality sources) are never corrected and propagate further errors as later entities are added
- The repair approach "outperforms other incremental approaches and achieves the same quality than with batch-like entity resolution showing that its results are independent from the order in which new entities are added"
- Evaluated on three real-world multi-source domains (geography: 3,054 entities/4 sources; music: 19,375/5 sources; persons: 10M/10 sources), across insertion-order permutations

**Key takeaways**
- Confirms the carrier-order concern is real and measurable, not speculative: streaming/incremental resolution without a repair mechanism systematically degrades quality relative to batch, and the degradation is attributable to insertion order specifically
- The repair-window pattern (bounded n-hop reclustering, not full batch re-run) is a concrete, cost-bounded template for premature-repair mitigation at KGF's ingest tier
- Cluster fusion (merging cluster members early for speed) trades away exactly the intra-cluster links that repair needs - a caution against over-eager materialization before identity is settled

**Tags**
- #EntityResolution #IncrementalER #KnowledgeGraphCompletion #ClusterRepair

**Source**
- Download: https://preprints.2020.eswc-conferences.org/121230352.pdf
- Local: [paper] famer incremental entity resolution, 2020.pdf
