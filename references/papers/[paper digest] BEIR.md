**BEIR: A Heterogeneous Benchmark for Zero-shot Evaluation of Information Retrieval Models, Thakur, Reimers, Rücklé, Srivastava, Gurevych (UKP-TUDA Darmstadt), 2021 (arXiv 2104.08663)**

Zero-shot IR benchmark spanning **18 datasets** across **9 retrieval tasks** (Wikipedia, biomedical, finance, news, Twitter, argument, entity, fact-checking, duplicate-question) - evaluates 10 systems across lexical/sparse/dense/late-interaction/re-ranking architectures. BM25 remains a strong zero-shot baseline: only cross-attentional re-ranking (BM25+CE, **+11%** average nDCG@10 over BM25, wins on **16/18** datasets) and document-expansion (docT5query, wins on **11/18**) beat it consistently. Dense bi-encoders generalize worst out-of-domain - TAS-B, the strongest dense model, beats BM25 on only **8/18** datasets despite leading BM25 in-domain on MS MARCO by up to **18 nDCG@10 points**.

**Key mechanism**
- 18 datasets across 9 tasks selected for diverse task type, domain, task difficulty, and annotation strategy (crowd-worker / expert / community-feedback derived) to stress zero-shot generalization rather than in-domain fit
- Standardizes every dataset to a common corpus/queries/qrels format and a single metric, nDCG@10, computed with the official TREC eval tool, so binary and graded-relevance datasets score comparably
- Evaluates 10 pretrained checkpoints in 5 architecture families: lexical (BM25/Anserini), sparse (DeepCT, SPARTA, docT5query), dense bi-encoder (DPR, ANCE, TAS-B, GenQ), late-interaction (ColBERT), re-ranking (BM25+CE, a 6-layer 384-h MiniLM cross-encoder distilled from a BERT-base/BERT-large/ALBERT-large teacher ensemble)
- Every neural model is trained or fine-tuned on MS MARCO (GenQ additionally domain-adapts via synthetic queries per target dataset) then scored with no further tuning on the remaining 17-18 datasets

**Main findings**
- Average nDCG@10 change vs. BM25 across the 18 datasets: BM25+CE +11%, ColBERT +2.5%, docT5query +1.6%, TAS-B -2.8%, GenQ -3.6%, ANCE -7.4%, SPARTA -20.3%, DeepCT -27.9%, DPR -47.7% (worst, wins on just 1/18)
- In-domain performance does not predict generalization: BM25 underperforms neural models by 7-18 nDCG@10 points in-domain on MS MARCO yet is competitive with, or beats, most of them out-of-domain
- Efficiency-quality tradeoff: BM25+CE and ColBERT need >350ms/query, 20-30x slower than dense (<20ms); dense models index at ~3GB/1M documents versus ColBERT's ~20GB/1M (~900GB projected for BioASQ's 15M documents, versus BM25's 18GB)
- TAS-B's training recipe (Margin-MSE loss plus in-batch negatives, distilled from a cross-encoder + ColBERT teacher pair) gives it the best dense zero-shot performance, beating ANCE on 14/18 and DPR on 17/18 datasets
- Annotation lexical bias: on TREC-COVID, dense models miss far more of the human-judged pool (Hole@10: TAS-B 31.8%, ANCE 14.4%) than lexical ones (BM25 6.4%, docT5query 2.8%); manually annotating the missing judgments lifts ANCE from 0.654 to 0.735 nDCG@10 (+6.7 points over BM25's own annotated score) and ColBERT by +5.8 points - the raw dense OOD scores are measurably pessimistic under lexically-biased qrels

**Key takeaways**
- Dense retrieval is fragile out-of-domain by BEIR's own numbers, but the same family is strongest in-domain: TAS-B beats BM25 by up to 18 nDCG@10 points on MS MARCO's native distribution and only falls behind once the domain shifts - the failure mode is domain shift, not dense embeddings as such
- Relevant to R47/H501: KGF's model-code identity problem is a short, salient-token matching task closer to BEIR's in-domain regime than its zero-shot OOD regime - a dense encoder exposed to the corpus's own vocabulary may already lexicalize model codes as near-unique embedding directions, which argues against assuming a separate sparse/GLiNER pass is required to catch them; the in-domain/out-of-domain split in this paper is direct support for H501's contrarian read
- The TREC-COVID Hole@10 study shows part of BEIR's dense-vs-lexical OOD gap is an annotation-pool artifact, not a pure capability gap - a caution against reading BEIR's raw zero-shot dense scores as the full picture
- Two-stage retrieve-then-rerank (BM25+CE) or late-interaction (ColBERT) is the safer generalization bet when domain shift is a real risk, at a 20-30x latency cost over dense bi-encoders

**Tags**: #BEIR #InformationRetrieval #ZeroShotRetrieval #DenseRetrieval #BM25 #DomainGeneralization #Benchmark

**Source**: https://arxiv.org/abs/2104.08663. Local: [paper] BEIR, 2021.pdf
