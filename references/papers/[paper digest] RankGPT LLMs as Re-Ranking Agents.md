**Is ChatGPT Good at Search? Investigating Large Language Models as Re-Ranking Agents, Sun, Yan, Ma, Wang, Ren, Chen, Yin, Ren, EMNLP 2023**

Establishes that a properly prompted GPT-4 beats the strongest supervised re-rankers zero-shot, and that its ranking behavior distills cleanly into a small model. GPT-4 with the paper's "permutation generation" prompt beats monoT5-3B by average nDCG **+2.7** (TREC), **+2.3** (BEIR), **+2.7** (Mr.TyDi); a **435M**-parameter DeBERTa student distilled from ChatGPT's permutations then beats monoT5-3B on BEIR by **+1.67** nDCG (**53.03** vs 51.36) and even surpasses its own ChatGPT teacher (49.37).

**Key mechanism**
- **Permutation generation (PG) prompting**: instead of asking the LLM to score or generate a query per passage (prior UPR/HELM-style approaches), the prompt shows a numbered list of passages and asks the model to directly output the passage identifiers in ranked order - a single generation call yields a full re-ordering, no log-probabilities required
- **Sliding window**: for candidate lists longer than context (typically top-100), a window (e.g. 20 passages, stride 10) slides from the end of the list to the front, re-ranking each window and carrying the top passages forward - makes listwise LLM ranking tractable beyond context length
- **NovelEval**: a 21-question test set built from post-training-cutoff web content (e.g. "which film won the 2023 Palme d'Or"), specifically to rule out the LLM having memorized the answer or its rank order from pretraining
- **Permutation distillation**: sample 10K queries x 20 BM25 candidates, get ChatGPT's permutation via PG, train a small model (DeBERTa or LLaMA-7B) with a RankNet loss against the teacher's inferred pairwise order - the student learns "how ChatGPT would rank" without needing ChatGPT's probabilities

**Main findings**
- GPT-4 zero-shot with PG beats supervised monoT5-3B and unsupervised baselines (UPR, InPars, Promptagator++) across TREC DL, 8 BEIR datasets, and 10-language Mr.TyDi
- PG strictly outperforms prior query-generation (QG) and relevance-generation (RG) prompting strategies on the same LLM (Table 4/5 ablation) - the framing of the prompt, not just model scale, is doing real work
- Sliding-window re-ranking is highly sensitive to initial candidate order: random or reversed BM25 input collapses nDCG@10 from 65.80 to ~25 - the LLM is refining an existing order, not ranking from scratch
- DeBERTa-Large distilled from ChatGPT permutations (53.03 BEIR avg nDCG) beats both monoT5-3B (51.36, same architecture family trained on human MS MARCO labels) and its own teacher ChatGPT (49.37) - the student's rankings are more stable than the LLM's noisy sampling
- Distillation from LLM-generated silver labels outperforms supervised training on human MS MARCO labels at every model size and data size tested (70M-435M params, 500-10K queries) - LLM permutations are a higher-quality training signal than the original relevance judgments

**Key takeaways**
- Permutation generation (direct list-of-IDs output) is the reference prompt design for any LLM-listwise-ranking component in KGF - cheaper and more effective than score-then-sort or query-likelihood approaches
- The distilled-student-beats-teacher result is the core justification for KGF's small-model scorer distillation direction: a 435M model trained on a large LLM's ranking behavior can out-rank both a same-size supervised model and the LLM itself, at a fraction of the inference cost
- Sliding-window re-ranking inherits and amplifies first-stage retrieval quality/order - a weak initial candidate list caps what any downstream listwise step can recover, reinforcing that KGF's retrieval-first ingest-time investment matters more than a strong reranker alone
- NovelEval's contamination-resistant construction (post-cutoff, novel facts) is a reusable pattern for validating that a scorer is reasoning rather than recalling memorized rank orders

**Tags**: #RankGPT #ListwiseReranking #PermutationDistillation #LLMReranker #ZeroShot #ScorerDistillation #EMNLP

**Source**: https://arxiv.org/abs/2304.09542. Local: [paper] RankGPT LLMs as Re-Ranking Agents, 2023-04.pdf
