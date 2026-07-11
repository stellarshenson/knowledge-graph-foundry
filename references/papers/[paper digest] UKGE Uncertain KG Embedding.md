# UKGE - Embedding Uncertain Knowledge Graphs

**arXiv 1811.10667 (AAAI 2019, UCLA, Chen et al.)**. First embedding model for UNCERTAIN knowledge graphs where every triple carries a confidence score (ConceptNet, NELL-derived NL27k, protein-interaction PPI5k): the model predicts a confidence value for ANY triple, seen or unseen - turning link prediction into confidence estimation over a graph whose edges are all provisional to some degree.

**Key mechanism**: embeddings map a triple's plausibility to a score fit against observed confidences (regression, not binary classification); probabilistic soft logic (PSL) rules inject soft constraints to estimate confidence for UNSEEN facts during training, so the model learns a calibrated-ish confidence surface over the whole candidate edge space rather than a decision boundary. Benchmarks: CN15k, NL27k, PPI5k; evaluated on confidence prediction (MSE) and uncertainty-aware ranking, beating deterministic KG embedding baselines adapted to the task.

**Main findings**: modeling the confidence value directly beats thresholding a deterministic model; soft-logic coupling of related facts materially improves unseen-fact confidence estimates - structure informs speculation.

**Key takeaways for KGF**: the representational substrate for a speculative edge tier - every provisional edge (SIMILAR_TO, hypothesized bridge, unverified extraction) is a (triple, confidence) pair, and a model over the committed graph can SCORE new speculative edges before any verifier spends tokens on them. Composes as the cheap-prior stage of a draft-verify ladder: UKGE-style scoring proposes/ranks, LLM or retrieval-outcome verifies, promotion follows Knowledge-Vault-style thresholds.

**Tags**: uncertain-kg, confidence-scores, link-prediction, provisional-edges, embeddings
**Source**: https://arxiv.org/abs/1811.10667 (PDF: `[paper] UKGE Uncertain KG Embedding, 2018-11.pdf`)
