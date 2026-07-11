# Knowledge Vault - web-scale probabilistic knowledge fusion with calibrated promotion

**KDD 2014 (Google, Dong et al.)**. Web-scale probabilistic KB: **1.6B candidate triples**, of which **324M at confidence >= 0.7** and **271M at >= 0.9** ("confident" tier; 271M of those not in Freebase). Every triple carries a CALIBRATED probability of correctness; the KB is explicitly a store of scored hypotheses, with a threshold defining the trusted tier.

**Key mechanism**: fusion of two independent evidence families - (1) extractors over text, HTML tables, page structure (DOM) and human annotations, and (2) GRAPH PRIORS computed from the existing KB: Path Ranking Algorithm (PRA, random-walk rule features, AUC **0.884**) and a neural embedding model (MLP, AUC **0.882**) each predict edge plausibility from graph structure alone - link prediction used as prior evidence for candidate facts. A supervised fusion layer combines extractor confidences with the prior into a calibrated posterior per triple.

**Main findings**: extractors and graph priors are complementary - fusing them yields markedly better calibrated confidence than either alone; per-source reliability weighting matters (the same fact from many low-quality extraction patterns is not the same as one high-quality source); calibration makes the confidence threshold an actual promotion policy rather than a heuristic.

**Key takeaways for KGF**: the industrial template for a speculative tier - EVERYTHING is admitted as a scored hypothesis, link-prediction priors from the committed graph re-score extractions, and only calibrated-high-confidence facts join the trusted tier. Maps directly to KGF: Bayesian resolver posterior = fusion layer; R38 calibration certificates = the calibration requirement; a spanning speculative edge is a prior-scored candidate awaiting evidence, exactly a KV low-confidence triple.

**Tags**: probabilistic-kb, knowledge-fusion, link-prediction-prior, calibration, two-tier-kb
**Source**: https://www.cs.ubc.ca/~murphyk/Papers/kv-kdd14.pdf (PDF: `[paper] Knowledge Vault, 2014-08.pdf`)
