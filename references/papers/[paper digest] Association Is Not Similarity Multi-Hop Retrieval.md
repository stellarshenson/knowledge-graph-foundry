**Association ≠ Similarity: Learning Corpus-Specific Associations for Multi-Hop Retrieval, Dury (independent), 2026 (arXiv 2604.20850)**

The applied test of PAM on real multi-hop QA, and the sharpest available evidence on both the promise and the limit of co-occurrence associations. **Association-Augmented Retrieval (AAR)** trains a 4.2M-parameter MLP with contrastive loss on passage pairs that co-occur as supporting facts for the same question, then reranks a dense candidate set by bi-directional association score blended with cosine.

**Key mechanism**
- Learn a passage-to-passage association function in embedding space from co-occurrence annotations over the target corpus
- At query time, rerank the dense top-N; adds **3.7 ms per query**, trains in under two minutes on one GPU, needs no LLM indexing

**Main findings**
- HotpotQA passage **Recall@5 0.831 → 0.916 (+8.6 points)** without evaluation-set tuning; gains concentrated on hard questions where the dense baseline fails (**+28.5 points**)
- MuSiQue **+10.1 points** in the transductive setting; downstream **+6.4 exact match**
- **The inductive variant - trained on training-split associations, evaluated on unseen validation associations - shows no significant improvement.** The method captures corpus-specific co-occurrences, not transferable ones
- Ablations: training on **semantically similar but non-associated** passage pairs degrades retrieval **below baseline**; shuffling association pairs causes severe degradation

**Key takeaways**
- Confirms the failure diagnosis exactly: dense retrieval handles query-relevance well and **passage-to-passage co-supporting relevance badly**, which is the middle-hop miss
- The gain source is supervision from **which passages co-occur as supporting facts for questions** - not generic textual co-occurrence. The inductive null says generic co-occurrence does not transfer
- The similar-but-not-associated ablation is a direct warning that co-occurrence edges built from surface proximity can be worse than no edges at all

**Tags**: #MultiHop #Association #CoOccurrence #HotpotQA #MuSiQue #InductiveNull #R59

**Source**: https://arxiv.org/abs/2604.20850. Local: [paper] Association Is Not Similarity Multi-Hop Retrieval, 2026.pdf
