**FIRST: Faster Improved Listwise Reranking with Single Token Decoding (2024)**

Listwise LLM rerankers generate a full ordered sequence of passage identifiers, which is accurate but slow and trains with a language-modeling loss that treats every ranking error uniformly. FIRST instead reads the ranking directly off the output logits of the *first* generated identifier token, paired with a learning-to-rank loss that prioritizes getting top ranks right. This cuts listwise reranking inference latency by **50%** while improving BEIR nDCG@10 to **54.3** (vs RankZephyr's 53.7), and the resulting ranked list is a stronger distillation signal for retriever relevance feedback than a cross-encoder's.

**Key mechanism**
- At inference, only the logits over the candidate-identifier vocabulary at the *first* decoding step are read; the full ranked order is recovered from these logits directly (no autoregressive generation of the whole sequence)
- Training combines the standard language-modeling loss with a weighted RankNet pairwise loss applied only to the first-token logits, weighted by inverse mean rank `1/(i+j)` so getting top-ranked pairs correct matters more than bottom pairs
- Base model is Zephyr-beta (7B, Mistral-based), fine-tuned 3 epochs on 40K GPT-4-labeled listwise examples derived from 5K MS MARCO queries; sliding window reranking with window 20, step 10
- Because ranking requires generating only one token instead of an entire ordered sequence, a much larger candidate set can be reranked in the same wall-clock budget
- Ranked output from the LLM reranker is also used as a relevance-feedback signal: the weighted RankNet loss is applied to optimize a query embedding for second-stage dense retrieval

**Main findings**
- BEIR nDCG@10 average: FIRST 54.3 vs RankZephyr 53.7, RankVicuna 50.7, cross-encoder baseline 50.7, using only Contriever top-100 as input
- Ablation: full joint loss (LM + weighted RankNet) 54.3 vs LM-only 52.3 vs weighted-RankNet-only (no LM) 51.7 - both loss terms are needed
- Loss choice matters: RankNet 56.7 average nDCG@10 (5-dataset subset) outperforms LambdaRank 55.4 and ListNet 55.9
- Relevance-feedback recall@100 after second-stage retrieval: LLM reranker (RankNet) feedback reaches 71.2% vs cross-encoder (KL divergence) feedback at 69.0%, and combining both signals (CE+LLM) reaches 72.0%, above either alone
- Inference speedup: single-token decoding accelerates reranking by 50% versus full-sequence listwise generation at matched ranking quality

**Key takeaways**
- Reading the ranking from first-token logits removes the dominant latency cost of listwise LLM reranking without sacrificing (and here slightly improving) ranking accuracy - a direct route to a cheap, fast scorer
- A pairwise learning-to-rank loss on top of the LM objective, not the LM objective alone, is what drives the accuracy gain; the efficiency gain is separable and comes purely from the decoding scheme
- Listwise LLM rerankers, even single-token ones, distill better into a dense retriever's query representation than cross-encoders do - ranking-sequence supervision carries more signal than a cross-encoder's scalar score

**Relevance**
- Directly actionable for R51 small-model scorer distillation: single-token-logit ranking is a cheap architecture for a KGF evidence-set scorer that needs to rank many candidate passages/entities per query without full-sequence generation cost
- The relevance-feedback result (LLM ranking as distillation signal beating a cross-encoder) suggests KGF could use a first-token reranker's output to fine-tune retrieval/entity-linking embeddings directly, rather than only consuming its ranked list at query time

**Tags**
- #Reranking
- #ListwiseRanking
- #InferenceEfficiency
- #LearningToRank
- #RelevanceFeedback

**Source**
- Download: https://arxiv.org/abs/2406.15657
- Local: [paper] FIRST Single-Token Listwise Reranking, 2024.pdf
