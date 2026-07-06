**VoG: Summarizing and Understanding Large Graphs (2014)**

VoG describes a large graph succinctly and surfaces its important structures with no task label. It uses a two-part MDL encoding over a vocabulary of subgraph primitives, admitting a candidate structure only if it decreases the total description length in bits. On multimillion-edge graphs, summaries of a few hundred structures both compress and reveal interpretable patterns.

**Key mechanism**
- Two-part MDL encoding L(M)+L(E|M) over a vocabulary of subgraph primitives (stars, full/near cliques, chains, bipartite cores)
- A candidate structure is admitted iff it decreases the total description length in bits
- Greedy selection (GNF/Top-k)

**Main findings**
- On multimillion-edge graphs (Flickr, Notre-Dame web), summaries of a few hundred structures compress and surface interpretable patterns
- MDL cleanly ranks which structures matter

**Key takeaways**
- The MDL fixed point - no candidate edit reduces bits - is a formal stopping certificate
- Bits-saved is a task-agnostic, per-edit-decomposable scalar
- A compression optimum is not a retrieval optimum

**Relevance**
- Canonical realization of an MDL stopping certificate - the fixed point where no candidate edit reduces bits IS "no structure left to explain"
- Supplies Phi_MDL(G) = bits-saved, a use-case-agnostic scalar with per-edit deltas computable at 2,800 nodes
- Warns that a compression optimum is not a retrieval optimum - motivating pairing with a task-conditioned potential

**Tags**
- #GraphSummarization #MDL #GraphMining

**Source**
- Download: https://arxiv.org/pdf/1406.3411
- Local: [paper] vog graph summarization mdl, 2014.pdf
