**LLM-Assisted Pseudo-Relevance Feedback, Otero, Parapar (IRLab CITIC, Universidade da Coruña), ECIR 2026 (arXiv 2601.11238)**

The gate that decides when a second feedback round is safe - an LLM relevance filter placed BEFORE RM3 expansion. Classical RM3 estimates an expanded query model from the top-k documents and interpolates it with the original query; it drifts when the top-k contains noisy or tangential documents. Pure-LLM query expansion instead risks hallucination and collection-vocabulary misalignment. The hybrid keeps RM3's corpus-grounded robustness but computes it only over the top-k documents an LLM judges relevant.

**Key mechanism**
- Run first-pass retrieval -> take top-k
- LLM judges each of the top-k as relevant/not (recognition-memory-style screening)
- RM3 term estimation runs ONLY over the accepted subset; interpolate with the original query (original query retains weight, per RM3)
- Re-issue expanded query for the final ranking

**Main findings**
- Beats blind PRF and a strong baseline across several datasets/metrics with a single cheap intervention
- The gain source is the FILTER, not new term generation: removing drift-inducing documents before expansion is what recovers robustness
- Keeps expansion terms grounded in the collection (no hallucinated vocabulary), unlike generate-only LLM QE
- RM3's original-query interpolation is retained - expansion never fully replaces the seed

**Relevance to KGF**
- The direct template for "what gates a second round" (family-1 research question): an LLM/recognition gate over the feedback pool BEFORE any amplification - the same move HippoRAG-2's seed filtering makes, here proven on PRF
- Confirms the drift fix is subtraction (filter bad feedback) not addition (generate more terms) - consistent with our fuse-add kill: the lever is cleaning the harvest, not enlarging the seed
- A FREE-to-GPU-trivial gate arm for R58: gate walk-success feedback (or a second dense pass) by a cheap relevance screen; the honest control is single-pass anchor-reset 0.8661/131 - a gated second round must clear it without drifting
- Interpolation-retains-seed echoes H597/PRF-pitfalls: original signal keeps majority weight

**Tags**: #PRF #RM3 #LLMFilter #SecondRoundGate #RecognitionMemory #AmplificationFamily1

**Source**: https://arxiv.org/abs/2601.11238. Local: [paper] LLM-Assisted Pseudo-Relevance Feedback, 2026.pdf
