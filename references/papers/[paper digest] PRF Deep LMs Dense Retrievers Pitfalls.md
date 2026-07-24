**Pseudo Relevance Feedback with Deep Language Models and Dense Retrievers: Successes and Pitfalls, Li, Mourad, Zhuang, Koopman, Zuccon (UQ / CSIRO), ACM TOIS 2022 (arXiv 2108.11044)**

The direct empirical study of PRF on DENSE retrievers - the closest published analogue of our fuse-add kill. PRF assumes top-ranked passages are relevant and folds them back into the query; the paper tests text-based, vector-based, and hybrid PRF over four datasets in retrieval and ranking. The headline pitfall is precisely ours: how much weight the feedback signal gets, and how deep the feedback pool is, decides whether PRF helps or drifts.

**Key mechanism**
- Text-based PRF: concatenate each feedback passage with the query, re-search, aggregate scores (Borda best); a single fused query underperforms per-passage-then-aggregate
- Vector-based PRF: average the query vector with feedback-passage vectors, weighted; re-score against the dense index (the exact operation family as our fuse-add into seed slots)
- Depth (how many top passages feed back) and query weight are the two decisive dials

**Main findings**
- Vector-based PRF helps dense retrievers ONLY when (i) the original query keeps the majority or equal weight in the combination, and (ii) the feedback pool is SHALLOW (few top passages) - a deep pool degrades effectiveness
- Text-based PRF on deep rerankers is mixed across datasets - it is not a free win; concatenate-and-aggregate beats a merged query
- The efficient vector-PRF recipe is a general, cheap method - but only inside the shallow-pool, query-dominant regime

**Relevance to KGF**
- This is the IR-side statement of H597: fusing feedback vectors INTO the query/seed representation is antagonistic unless the original signal dominates and the feedback pool is tiny - "merge the harvest, never the seeds" is the same lesson learned in dense-PRF terms (query must keep majority weight; deep pools drift)
- Maps the DRIFT failure directly onto our fuse-add -1.6pp kill: aggressive/deep vector averaging is where dense PRF breaks, exactly where our fuse-ADD into seed slots broke
- Prescribes the safe envelope for any family-1 second-round mechanism: shallow feedback, query-dominant weighting, per-item scoring then aggregate - never a single averaged query vector
- The KILL clause for R58 family 1: any re-injection of walk-success evidence into the SEED/query vector must beat H627 smoothing AND must not deep-average; the moment it dilutes the seed it is the documented pitfall

**Tags**: #PRF #DenseRetrieval #QueryDrift #FuseAddFence #AmplificationFamily1

**Source**: https://arxiv.org/abs/2108.11044. Local: [paper] PRF Deep LMs Dense Retrievers Pitfalls, 2021.pdf
