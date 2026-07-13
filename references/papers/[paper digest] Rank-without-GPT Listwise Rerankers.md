**Rank-without-GPT: Building GPT-Independent Listwise Rerankers on Open-Source Large Language Models, Zhang, Hofstätter, Lewis, Tang, Lin, EMNLP 2023 Findings**

Shows that listwise reranking effectiveness does not require any GPT dependency (direct inference or distillation teacher), and pins down what actually bottlenecks a listwise reranker: training-data ranking quality, not model size or GPT lineage. The largest GPT-independent student (34B, teacher-free "co.rerank" pipeline) surpasses GPT-3.5-based listwise rerankers by **13%** and reaches **97%** of GPT-4-based reranker effectiveness (nDCG@10, TREC-DL-19/20), and just **5K** training queries already deliver **97%** of the effectiveness obtained with 10K.

**Key mechanism**
- **co.rerank**: a listwise reranking pipeline that generates its own silver training labels without any GPT model in the loop - existing pointwise-labeled IR data (e.g. raw MS MARCO relevance judgments) is shown to be insufficient for training a listwise reranker, so the paper instead uses rankings produced by a strong non-GPT ranker as silver listwise supervision
- Fine-tunes Code-LLaMA-Instruct (7B/13B/34B) with QLoRA (or full fine-tuning in an ablation) using a RankNet-style loss over the sliding-window listwise task, same paradigm as RankVicuna/RankGPT but with the GPT link removed at both the teacher and base-model level
- **Enriched judgments**: because listwise rerankers surface more unjudged passages than pointwise ones at the top of the ranked list (Judged@10 0.88-0.94 vs >0.98), the authors manually add missing relevance labels for the top-10 of several systems' output and re-score - correcting an evaluation blind spot rather than just reporting raw benchmark numbers
- Data-quality experiment: trains identical listwise architectures on (a) ground-truth pointwise MS MARCO labels only, (b) silver rankings from progressively stronger pointwise rerankers - effectiveness tracks the quality of the ranking source almost 1:1, with no sign of plateauing

**Main findings**
- Training on raw pointwise ground-truth labels alone gives markedly worse listwise rerankers than training on silver rankings from a competent pointwise reranker - the listwise student's ceiling tracks its training data's ranking quality, not just the label's binary relevance signal
- Scaling training data from 2K to 5K queries yields most of the achievable gain (97% of the 10K-query result); 10K to 20K brings marginal or no further improvement on TREC-DL-19/20 - listwise fine-tuning is not data-hungry once past a small threshold
- Scaling model size (7B to 13B to 34B, fixed 10K training data) gives steady but modest gains: nDCG@10 0.722 to 0.737 to 0.743 (DL19), 0.674 to 0.683 to 0.687 (DL20) - the 13B model already surpasses its silver-label teacher
- On enriched judgments, the 7B GPT-independent reranker (71.8/67.4 nDCG@10, DL19/20) is statistically indistinguishable from RankGPT-4 (75.7/71.0) despite the score gap, and clearly beats RankGPT-3.5/RankVicuna/LRL
- Listwise rerankers trap more relevant passages in local blocks of the sliding window (visualized via heatmap of input-position vs output-position) than pointwise rerankers, which redistribute more symmetrically - a structural property of the sliding-window mechanism itself, independent of teacher

**Key takeaways**
- The core message for KGF's scorer-distillation track: what you distill from (ranking-quality of the silver source) dominates which model produced it - a competent open pointwise reranker is an adequate teacher, GPT is not a structural requirement
- 5K queries is a useful data-budget anchor for any small-model reranker/scorer fine-tune KGF runs - beyond that, more data buys little without also improving label quality
- The "enriched judgments" correction is a reusable methodology lesson: raw benchmark nDCG understates a listwise system's true quality whenever it promotes passages the original judgment pool never saw - relevant to interpreting KGF's own bench-ladder scores against systems with denser judgment pools
- The sliding-window "trapping" artifact is a known structural limitation to account for if KGF adopts sliding-window listwise scoring for large candidate sets rather than single-pass whole-set scoring (cf. Set-Encoder's non-windowed alternative)

**Tags**: #ListwiseReranking #GPTIndependent #ScorerDistillation #TrainingDataQuality #OpenSource #EMNLP

**Source**: https://arxiv.org/abs/2312.02969. Local: [paper] Rank-without-GPT Listwise Rerankers, 2023-12.pdf
