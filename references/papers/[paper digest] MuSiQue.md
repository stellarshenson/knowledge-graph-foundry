**MuSiQue: Multihop Questions via Single-hop Question Composition (Trivedi et al., TACL 2022)**

Builds a **25K 2-4 hop QA dataset (MuSiQue-Ans)** by bottom-up composition of connected single-hop questions, engineered so that each hop critically depends on a **bridge entity** produced by the previous hop - and shows existing multihop benchmarks are largely solvable by disconnected shortcuts that never traverse the bridge.

**Key mechanism**
- Bottom-up composition: pick pairs of single-hop questions where hop-2 needs hop-1's answer (the bridge entity) as input, discarding pairs answerable independently
- Bridge-entity dependency is the construction invariant - the answer to sub-question 1 is the entity that sub-question 2 is asked about
- Unanswerable contrast set (MuSiQue-Full) built by removing the paragraph carrying the bridge entity, so the only difference between answerable and unanswerable is bridge-entity presence
- Fine-grained control over hop count and composition structure (chain vs star)

**Main findings**
- MuSiQue-Ans is 3x harder (human-machine gap) than prior multihop sets
- A single-hop (disconnected-reasoning) model suffers a **30-point F1 drop** vs on shortcut-friendly datasets - direct measure of how much prior benchmark accuracy came from skipping the bridge
- Removing the bridge-entity paragraph is the operationalized definition of the multihop failure: no bridge -> no connected reasoning -> unanswerable
- Decompositions come free from the construction and expose per-hop supporting facts (first-hop fact vs bridge fact vs final-hop fact)

**Key takeaways**
- The standard multihop failure diagnosis is **bridge-entity centric**: multihop failure = failure to retrieve/traverse the bridge entity that links hop-1 to hop-2, distinct from failing the first hop's lookup
- "Disconnected reasoning" is the field's name for answering without the bridge - the failure the atlas's traversal axis should localize

**Relevance to KGF atlas (R57)**
- Answers Question (E): the standard multihop failure taxonomy is first-hop-lookup vs bridge-traversal vs final-hop, with the **bridge entity** as the load-bearing failure locus - MuSiQue makes bridge-removal the very definition of unanswerable
- Directly motivates a **bridge-role axis** for the atlas: tag each missed gold entity as first-hop / bridge / terminal-answer. Our current traversal axis (hop distance to retrieved-region boundary, on/off-path, PPR mass rank) measures *where* a carrier sits but not *what reasoning role* it plays - a bridge miss and a terminal miss have the same hop coordinate but different downstream cost
- Cross-check for the **boundary+1 concentration** claim: bridge entities are structurally one hop past the first-hop anchor's neighborhood, so a bridge-heavy miss profile would *predict* boundary+1 clustering - MuSiQue supplies the mechanism our claim currently states only geometrically
- Anchor-reset seeding (H583/H597) is a bridge-traversal remedy: resetting the walk from question anchors is precisely the reachability path to the bridge entity that disconnected retrieval skips

**Tags**: multihop-qa, bridge-entity, disconnected-reasoning, first-hop-vs-bridge, dataset, traversal-failure

**Source**: https://arxiv.org/abs/2108.00573
