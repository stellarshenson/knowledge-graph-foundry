**Predictive Associative Memory: Retrieval Beyond Similarity Through Temporal Co-occurrence, Dury (Eridos), 2026 (arXiv 2602.11322)**

The framework paper for "association is not similarity". Similarity retrieval assumes useful memories are similar memories; PAM instead trains a JEPA-style predictor on **temporal co-occurrence** within an experience stream, so retrieval answers "which regions of meaning space are reachable from this state", not "which are nearest".

**Key mechanism**
- An **Inward JEPA** predicts associatively reachable *past* states, complementing the standard Outward JEPA that predicts future states
- Association weight is co-occurrence **relative to a familiarity baseline**: `w_assoc(s_i,s_j) = w_raw(s_i,s_j) - E[w_raw(s_i,s_j)]`; only co-occurrence above the expected baseline counts as a real association (sensory-adaptation analogy)
- Adaptive decay removes stale associations

**Main findings** (synthetic navigation benchmark)
- Association Precision@1 = **0.970** - the top retrieval is a true temporal associate 97% of the time
- **Cross-boundary Recall@20 = 0.421 where cosine similarity scores exactly zero**
- Discrimination AUC experienced-together vs never-experienced-together **0.916 vs cosine 0.789**; restricted to cross-room pairs where embedding similarity is uninformative, **0.849 vs cosine 0.503 (chance)**
- Specificity control against similar-but-not-associated distractors: AUC 0.848 vs cosine 0.732
- Temporal-shuffle control collapses cross-boundary recall by **90%**, confirming the signal is co-occurrence structure and not embedding geometry
- Results stable across seeds (SD < 0.006)

**Key takeaways**
- Direct evidence that a co-occurrence-derived association channel recovers items a dense channel **provably cannot** - the bridge-entity failure class stated in general form
- The baseline subtraction is the published answer to "which associative links are worth keeping": co-occurrence in excess of expectation, not raw co-occurrence
- The benchmark is **synthetic**; no text-corpus or QA evaluation, so the magnitudes do not transfer, only the mechanism

**Tags**: #AssociativeMemory #CoOccurrence #BridgeEntities #JEPA #Synthetic #R59

**Source**: https://arxiv.org/abs/2602.11322. Local: [paper] Predictive Associative Memory Temporal Co-occurrence, 2026.pdf
