**Learning Passage Impacts for Inverted Indexes (DeepImpact), Mallia, Khattab, Suel, Tonellotto, SIGIR 2021**

DeepImpact learns a single per-term impact score directly optimized for ranking, replacing term-frequency-based scoring. It outperforms first-stage retrieval baselines by up to 17% on effectiveness metrics versus DocT5Query, and when used as a first-stage ranker ahead of a ColBERT re-ranker matches or beats ColBERT end-to-end (E2E) effectiveness while delivering a 4.4x-5.1x speedup.

**Key mechanism**
- Combines DocT5Query's document expansion with a directly-learned impact score, rather than reusing BM25 term-frequency scoring (DocT5Query) or training a per-token frequency regression (DeepCT)
- Uses only the "Inject" half of DocT5Query (adds new terms likely to appear in relevant queries) rather than "Rewrite" (which reweights existing term frequencies); the document then holds original + injected terms
- BERT-base encodes original terms (white) and injected terms (gray), separated by [SEP]; the first occurrence of each unique term feeds a 2-layer MLP with ReLU (the Impact Score Encoder), producing one scalar impact value per unique term in the document
- Document-query score = sum of the impact scores for terms in the intersection of query and document terms - no term frequency, no IDF, no per-document normalization
- Trained on MS-MARCO triples (query, relevant passage, non-relevant passage) with pairwise softmax cross-entropy loss over the two documents' summed scores, optimizing the score gap between relevant and non-relevant passages directly rather than per-token regression targets
- Training config: BERT-base, learning rate 3e-6, Adam optimizer, batch of 32 triples, 100,000 iterations, max input length 160 tokens
- Impact scores are quantized to b=8 bits (linear quantization, range [1, 2^b-1]) at index time with no noticeable precision loss, then summed at query time - fully compatible with a standard inverted index (Anserini/CIFF export, PISA with MaxScore query processing)

**Main findings**
- MSMARCO Dev Queries, first-stage retrieval: DeepImpact MRR@10 0.326 vs DocT5Query 0.278, DeepCT 0.244, BM25 0.188; NDCG@10 0.385 vs 0.338/0.298/0.235 - all improvements over prior methods statistically significant (Bonferroni-corrected, p<0.05)
- TREC 2019: DeepImpact NDCG@10 0.695, MAP 0.456 vs DocT5Query 0.648/0.405; TREC 2020: NDCG@10 0.651, MAP 0.426 vs DocT5Query 0.619/0.408
- First-stage recall@1000: DeepImpact 0.948 vs DocT5Query 0.947, DeepCT 0.910, BM25 0.858 - the recall gap widens at smaller cutoffs (recall@10: 0.584 DeepImpact vs 0.542 DocT5Query, 0.484 DeepCT, 0.394 BM25)
- Re-ranking DeepImpact's candidates with ColBERT beats ColBERT E2E (ANN-based first stage) on NDCG@10 across MSMARCO Dev (0.425 vs 0.424), TREC 2019 (0.722 vs 0.694), and TREC 2020 (0.691 vs 0.676), while running 4.4x-5.1x faster (e.g. mean response time 81.00ms vs 380.97ms on MSMARCO Dev)
- Ablation (Table 1) shows DocT5Query's Rewrite component alone reaches stronger MRR@10 (0.215) than Inject alone (0.194), but Inject reaches higher recall (0.912 vs 0.878); DeepImpact's design keeps Inject for vocabulary coverage and learns the impact weighting instead of relying on Rewrite
- DeepImpact's own first-stage mean response time is higher than BM25/DeepCT/DocT5Query (58.64ms vs 12.62ms on MSMARCO Dev) because its learned score distribution is not exploited as efficiently by the MaxScore query processing algorithm - flagged by the authors as open efficiency work

**Key takeaways**
- A single scalar impact per term, jointly optimized for the ranking objective (softmax cross-entropy over summed query-term scores across a relevant/non-relevant pair), replaces term-frequency-derived scoring entirely - no BM25-style TF or IDF component survives in the final score
- This is DF-independent: unlike BM25/DeepCT, nothing in the score formula normalizes by document frequency or corpus statistics - the impact is a property of the (term, document) pair alone, learned end-to-end
- The optimization target is the score gap between relevant and non-relevant passages summed across the full query, not a per-token regression to a synthetic frequency label (DeepCT's approach) - directly optimizing what the downstream ranker needs rather than a proxy
- Document expansion and impact weighting are separable and stack: Inject supplies vocabulary coverage for terms absent from the original text, the learned impact head supplies the weighting - both contribute independently to the effectiveness gains
- R47 relevance: DeepImpact is the load-bearing precedent for R47-H508's learned-impact weighting over span tokens - a single per-token scalar, trained end-to-end against a ranking loss rather than derived from occurrence counts, computed once at ingest time, quantized, and summed at query time with zero query-time model calls; the same pattern (learn one impact scalar per span token, store it, sum at retrieval) transfers directly

**Tags**: #DeepImpact #LearnedSparseRetrieval #InvertedIndex #DocumentExpansion #TermWeighting #SIGIR

**Source**: https://arxiv.org/abs/2104.12016
