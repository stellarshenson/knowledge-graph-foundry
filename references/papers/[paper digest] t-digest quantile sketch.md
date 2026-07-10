**Computing Extremely Accurate Quantiles Using t-Digests, Dunning, Ertl, 2019 (arXiv 1902.04023)**

The practitioner's quantile sketch: an online, mergeable summary of a score distribution whose accuracy is RELATIVE to max(q, 1−q) rather than absolute - near-constant relative error at the tails, which is where gate thresholds live. Data is compressed into weighted centroids whose maximum size is governed by a scale function with a single compression parameter δ; for the k1 scale function a fully merged t-digest holds at most **⌈δ⌉** clusters (lower bound near ⌊δ/2⌋), independent of stream length.

**Key mechanism**
- Scale function forces clusters near q = 0 and q = 1 to be tiny (down to single samples) and lets mid-distribution clusters grow - tail quantiles stay sharp, memory stays bounded
- Two build modes: buffer-and-merge (statically allocated, amortized fast) and clustering-style incremental insertion
- Separately computed digests over different data sections combine "with no loss in accuracy" - the merge property that makes per-ingestion sketches composable into a corpus-class sketch
- Estimation error for quantile q scales with q(1−q), vs earlier sketches (Q-digest, GK) whose error is uniform in q

**Main findings**
- Robust on skewed and ordered inputs, where naive streaming quantile estimators degrade
- Reference implementations in Java, Go, Python; the de facto standard in monitoring systems
- No worst-case space guarantee proof of KLL strength - t-digest trades theoretical optimality for tail accuracy and engineering maturity

**Key takeaways**
- For KGF calibration persistence: one t-digest per corpus class over the UNLABELED gate-signal stream (every retrieval evaluates the signal for free) captures the score distribution across ingestions in ~kilobytes on the graph node
- Enables label-free drift checks (compare new ingestion's digest quantiles against the stored class digest) and threshold→quantile mapping (express θ = 0.765 as "the 25th percentile of class scores" and re-derive θ after shift)
- Merge-on-ingest = update-not-refit: exactly the "keep calibration information for future ingestions" requirement for the distributional half of the state

**Tags**: #QuantileSketch #tDigest #Streaming #Mergeable #Monitoring

**Source**: https://arxiv.org/abs/1902.04023. Local: [paper] t-digest quantile sketch, 2019-02.pdf
