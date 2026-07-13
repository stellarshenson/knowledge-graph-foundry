**SPLADE v2: Sparse Lexical and Expansion Model for Information Retrieval, Formal, Piwowarski, Lassance, Clinchant, 2021**

Builds on the original SPLADE (SIGIR 2021) sparse-retrieval model by swapping its pooling mechanism, adding a document-only variant, and applying cross-encoder distillation. Gains exceed **9% NDCG@10** over the original SPLADE on TREC DL 2019, and the distilled model (DistilSPLADE-max) reaches **MRR@10 0.368** on MS MARCO dev / **NDCG@10 0.729** on TREC DL 2019 - competitive with dense SOTA (RocketQA MRR@10 0.370) and best-on-dataset on **11 of 14** BEIR corpora at zero-shot avg NDCG@10 **0.506**, beating tuned BM25 (0.456) and ColBERT (0.457).

**Key mechanism**
- Term importance predicted per input token via the BERT MLM head: w_ij = transform(h_i)^T E_j + b_j over the full WordPiece vocabulary (|V| = 30522)
- Per-vocabulary-term weight aggregated across the input sequence with log-saturation: w_j = sum_i log(1 + ReLU(w_ij)); original SPLADE uses sum pooling over i
- SPLADE v2 replaces sum with max pooling: w_j = max_i log(1 + ReLU(w_ij)) -> SPLADE-max, closer in spirit to SPARTA/EPIC/ColBERT
- FLOPS regularizer (Paria et al. 2020) penalizes squared average per-term activation probability, balancing posting-list length across the index; separate lambda_q / lambda_d weights push more sparsity onto queries than documents
- SPLADE-doc variant drops query expansion/term weighting entirely - score is the sum of document term weights over query terms only, so the full document representation is precomputable offline with no query-side inference
- DistilSPLADE-max: two-stage distillation - train a SPLADE retriever plus a cross-encoder reranker (ms-marco-MiniLM-L-12-v2) on Hofstatter-style triplets, then retrain SPLADE from scratch on SPLADE-mined hard negatives scored by the reranker via Margin-MSE loss

**Main findings**
- MS MARCO dev MRR@10: BM25 0.184 -> original SPLADE 0.322 -> SPLADE-max 0.340 -> DistilSPLADE-max 0.368; Recall@1000 rises 0.853 -> 0.955 -> 0.965 -> 0.979
- TREC DL 2019 NDCG@10: BM25 0.506 -> SPLADE 0.665 -> SPLADE-max 0.684 -> DistilSPLADE-max 0.729
- Max pooling alone adds almost 2 points MRR@10/NDCG@10 over sum-pooled SPLADE
- SPLADE-doc matches original SPLADE effectiveness (MRR@10 0.322, no query encoder); at higher sparsity reaches MRR@10=29.6 with an average of only 19 non-zero document weights, still beating doc2query-T5
- BEIR avg NDCG@10 (14 datasets, all/zero-shot): BM25 0.440/0.456, TAS-B 0.435/0.437, ColBERT 0.455/0.457, SPLADE-sum 0.446/0.451, SPLADE-max 0.460/0.464, DistilSPLADE-max 0.500/0.506 - best-on-dataset counts 2 (BM25), 2 (ColBERT), 11 (DistilSPLADE-max)

**Key takeaways**
- Max pooling over log-saturated MLM-logit impacts, not sum pooling, is what makes SPLADE competitive - a one-line aggregation change is worth ~2 points MRR@10
- Learned sparsity plus implicit expansion beats tuned BM25 by a wide margin (zero-shot NDCG@10 0.506 vs 0.456) while keeping an inverted-index-compatible representation - this is the learned-sparse bar R47 must clear, not BM25 itself (Failure Mode B: beating BM25 alone does not clear the modern sparse baseline)
- The document-only encoder (SPLADE-doc) shows expansion/impact scoring can be pushed entirely to ingest time with competitive results, matching KGF's retrieval-first, ingest-heavy cost profile
- Distillation from a cross-encoder is the single largest lever measured in the paper (MRR@10 0.340 -> 0.368), ahead of the pooling change or FLOPS regularization tuning

**Tags**: #SPLADE #LearnedSparseRetrieval #DocumentExpansion #FLOPS #Distillation #BEIR #MSMARCO

**Source**: https://arxiv.org/abs/2109.10086. Local: [paper] SPLADE v2, 2021.pdf
