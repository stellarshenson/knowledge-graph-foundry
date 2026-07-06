**On Over-Squashing in Message Passing Neural Networks: The Impact of Width, Depth, and Topology (2023)**

This paper disentangles whether width, depth, or topology controls over-squashing. Sensitivity bounds show over-squashing between two nodes is governed by commute time (equivalently effective resistance): width mitigates only modestly, depth cannot help because vanishing gradients dominate first, and topology plays the greatest role. It unifies existing rewiring methods as commute-time reducers.

**Key mechanism**
- Sensitivity bounds tie over-squashing between two nodes to their commute time (equivalently effective resistance)
- Width mitigates modestly at the cost of overall sensitivity
- Depth cannot help - vanishing gradients dominate first
- Topology plays the greatest role

**Main findings**
- Existing rewiring methods unify as commute-time reducers
- High-commute-time pairs are exactly the ones GNNs fail to connect

**Key takeaways**
- Where reach is trivial, depth and diffusion are provably powerless
- Commute time is the single quantity that governs the failure
- The theory justifies shallow designs on well-connected graphs

**Relevance**
- Our retrieval sits at near-zero commute time (91% of evidence on-seed, 100% within 2 hops) - this theorem is the mathematical justification for the shallow design and for PPR adding nothing
- Usable residue: commute time from an un-retrieved gold node to the seed set distinguishes topological blind spots from embedding/seed-selection failures

**Tags**
- #OverSquashing #CommuteTime #GNN #GraphTopology

**Source**
- Download: https://arxiv.org/pdf/2302.02941
- Local: [paper] over-squashing width depth topology, 2023.pdf
