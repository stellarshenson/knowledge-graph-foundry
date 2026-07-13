**Distilling a Small Utility-Based Passage Selector to Enhance Retrieval-Augmented Generation, Zhang, Bi, Guo, Zhang, Wang, Yin, Cheng, SIGIR-AP 2025**

Replaces fixed top-k relevance ranking with a distilled small model that directly selects a variable-size set of passages by predicted usefulness for answer generation, not topical relevance. Distilled from Qwen3-32B into a **1.7B** student (UtilityQwen), the selector beats every fixed-k cutoff of a same-size relevance ranker (RankQwen-1.7B) on HotpotQA evidence quality (Micro-F1 **60.58** vs RankQwen's best of 41.70 at top-5) and downstream answer F1 (**53.56** vs 49.68), while eliminating the need to tune k at all.

**Key mechanism**
- **Utility, not relevance**: relevance measures topical query-passage match; utility measures whether a passage actually helps generate a correct, complete answer - the two diverge sharply on multi-hop questions requiring several complementary passages, which is exactly the "set selection" problem (a single relevant-but-insufficient passage scores high on relevance, low on utility)
- **Selection instead of ranking**: the student model outputs a variable-size selected set per query rather than a score to threshold - avoids the fixed-k hyperparameter, which the paper shows has no single good value across query complexity (optimal k differs for NQ vs HotpotQA, Figure 1)
- **Forward-propagating sliding window** (window w=20, stride s=10): unlike ranking's backward bubble-sort-style window, utility selection moves front-to-back; each window's LLM judges utility of w passages and selects some, selections are prepended to a running "preselected queue," and the next window carries forward s already-selected passages plus new unprocessed ones - preserves selection quality because pseudo-answer generation (used to judge utility) needs high-quality passages in context, and processing front-to-back keeps the best material flowing forward
- **Joint distillation objective**: the teacher (Qwen3-32B) generates both a pseudo-answer and a utility judgment per window; the student is trained to imitate both jointly, because utility judgment depends on being able to generate a plausible pseudo-answer from the candidate set - selection ability is bottlenecked by generation ability, not learnable from labels alone
- Malformed-generation filtering during teacher-label collection (dropping bad list formats, missing IDs, repeats) follows the RankZephyr recipe, plus noisy embeddings during instruction fine-tuning

**Main findings**
- On HotpotQA (multi-hop), UtilityQwen1.7B's selected-evidence Micro-F1 (57-61%) and downstream EM/F1 beat every top-k cutoff of RankQwen1.7B, a same-size model distilled for relevance ranking instead of selection - the paper's central claim, that utility beats relevance for complex queries, replicates with two different generators (Llama-3.1-8B, Qwen2.5-7B) and two retrievers (BM25, BGE)
- On NQ (simple, single-hop), there is no statistically significant difference between utility-based selection and a well-tuned relevance-ranking top-k - the utility advantage is specific to queries needing a coherent multi-passage evidence set, not a universal win
- Stronger first-stage retrieval (BGE > BM25) widens the utility-selector's margin over the ranker more than it does for a fixed-k ranker - better candidates let the student generate better pseudo-answers, directly improving its judgment quality
- Teacher-vs-distilled-student gap is larger for utility selection than for relevance ranking (Table 4: Qwen3-32B teacher selection F1 75.24 vs UtilityQwen1.7B's 60.58, a bigger relative drop than ranking's teacher-student gap) - utility judgment is a harder capability to distill than relevance scoring, leaving headroom for a stronger backbone or more distillation data
- RankQwen1.7B (the ranking half of the same distillation) separately beats ChatGPT by 5.5% nDCG@10 on BEIR average, confirming Qwen3-32B is a competent ranking teacher independent of the utility-selection result
- UtilityQwen1.7B's selected-set size adapts per query (average 4.98 passages for HotpotQA, 11.31 for NQ) - it learns query-complexity-dependent set sizing without being told k

**Key takeaways**
- Directly actionable for R51's "set selection" theme: a small distilled model choosing a variable-size evidence set by utility, not a fixed top-k by relevance score, is the mechanism to adopt for KGF's retrieval-to-generation handoff on multi-hop queries
- The forward sliding window with a persistent "selected queue" is a concrete, cheap pattern for letting a small scorer condition later decisions on earlier selections within one linear pass - a lighter-weight alternative to the Set-Encoder's shared-token cross-attention for sequential set-building tasks
- Joint pseudo-answer-generation + judgment distillation (the model must learn to generate before it can judge) is a training-objective coupling worth testing whenever KGF distills a small judge/selector from a larger LLM teacher
- The teacher-student gap being wider for utility than for ranking is a sizing signal: if KGF's small-model scorer needs to do utility-style set judgments rather than pairwise relevance, budget for a larger student or more teacher-label volume than a pure reranker would need

**Tags**: #UtilitySelection #ScorerDistillation #SetSelection #RAG #SlidingWindow #MultiHop #SIGIR

**Source**: https://arxiv.org/abs/2507.19102. Local: [paper] Distilling Utility-Based Passage Selector, 2025-07.pdf
