**RankZephyr: Effective and Robust Zero-Shot Listwise Reranking is a Breeze!, Pradeep, Sharifymoghaddam, Lin, University of Waterloo, 2023**

A **7B**, fully open-source listwise reranker distilled from RankGPT-4 that matches and in several settings beats its "rumored two orders of magnitude larger" proprietary teacher, while being deterministic and reproducible. On TREC DL19/20 reranking SPLADE++ candidates, RankZephyr reaches nDCG@10 **0.7816** (single pass) / **0.7855** (progressive triple-pass, "RankZephyr-rho"), against RankGPT-4's **0.7464**/0.7076 - and against RankLLaMA-13B, a strong pointwise 13B model, RankZephyr wins despite needing no human relevance labels.

**Key mechanism**
- Instruction fine-tunes Zephyr-7B (not Vicuna - an ablation shows Zephyr is the stronger base model) on RankGPT-4-generated permutation orderings, following the RankVicuna recipe but swapping teacher and base model
- **Variable window-size training**: trains on shuffled/varied sliding-window sizes rather than one fixed window, so the model generalizes robustly to whatever window/stride is used at inference - fixed-window training catastrophically fails at unseen window sizes (38.7% well-formed outputs vs 98.9% for variable-window training on a mismatched 10/5 config)
- **Progressive reranking (RankZephyr-rho)**: re-runs the full sliding-window pass over the candidate list multiple times (here, three), each pass refining the previous ranking - consistently improves over a single pass
- Teacher/training-source ablation: RankGPT-4 teacher beats RankGPT-3.5 teacher; ADA2 first-stage orderings as training input slightly outperform BM25 orderings; discriminative (hard) query sampling gives no measurable gain over random sampling
- Deterministic inference (zero temperature, no sampling variance) versus RankGPT-4's non-deterministic API outputs, reported as an average over 3-6 runs in the paper this compares against

**Main findings**
- In-domain (MS MARCO v1, DL19/DL20): RankZephyr beats RankGPT-4 and RankLLaMA-13B; relative nDCG gains of up to 15% over first-stage retrieval when reranking higher-quality candidate lists
- Out-of-domain (MS MARCO v2 DL21/22, BEIR NEWS/COVID): RankZephyr still improves substantially over its first-stage retriever, but underperforms RankGPT-4 specifically here - attributed to a smaller training context window (4096 vs GPT-4's 8192) and 2-4 points lower Judged@10
- First-stage retrieval quality matters more than reranker sophistication at the margin: reranking a stronger first-stage retriever (SPLADE++, RepLLaMA) yields smaller relative gains (7-20%) than reranking a weak one like BM25 (45-55%) - diminishing returns as the candidate list improves
- Output well-formedness is a real, measurable failure mode: fixed-window RankZephyr produces malformed responses (missing/repeated document IDs) far more often outside its trained window size; variable-window training essentially eliminates this
- Judged@10 (fraction of top-10 output passages that have a human relevance label) is systematically lower for listwise rerankers (0.88-0.94) than for pointwise ones (>0.98) - listwise models surface unjudged documents more often, meaning reported nDCG@10 for listwise systems is a lower bound

**Key takeaways**
- A 7B open-source student distilled from a much larger proprietary teacher, trained with output-format robustness explicitly engineered in (variable window sizes), is a directly applicable recipe for KGF's small-model scorer distillation track - format robustness is a first-class training objective, not an afterthought
- Progressive/multi-pass reranking (rho) is a cheap effectiveness lever - re-running the same small model over its own output before committing - worth testing against KGF's single-pass scoring calls
- The Judged@10 gap is a caution for benchmark-only evaluation regimes: listwise rerankers surface different (unjudged) passages than the systems the judgment pool was built from, so a benchmark's reported score for a new listwise method understates its true effectiveness
- Diminishing reranking returns on strong first-stage retrieval reinforces that KGF's ingest-time investment (retrieval-first principle) dominates reranker choice once first-stage quality crosses a threshold

**Tags**: #RankZephyr #ListwiseReranking #ScorerDistillation #OpenSource #ProgressiveReranking #ZeroShot

**Source**: https://arxiv.org/abs/2312.02724. Local: [paper] RankZephyr Zero-Shot Listwise Reranking, 2023-12.pdf
