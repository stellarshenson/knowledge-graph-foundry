**Optimal Quantile Approximation in Streams (KLL), Karnin, Lang, Liberty, FOCS 2016 (arXiv 1603.05346)**

The theoretical optimum for streaming quantiles: a randomized sketch that answers any rank query within additive error εn with probability ≥ 1−δ using **O((1/ε) log log(1/δ))** space, with a matching lower bound - closing a problem open since Munro-Paterson (1980). Prior best was O((1/ε) log(1/ε)) (Felber-Ostrovsky); the best deterministic algorithm (Greenwald-Khanna) needs O((1/ε) log(nε)) and grows with stream length. KLL's space is independent of n.

**Key mechanism**
- Hierarchy of compactors: each buffer of capacity k halves its content by keeping every other item (random offset) and promoting survivors upward with doubled weight
- Capacities decay geometrically down the hierarchy; only the top O(log log) levels need full-size buffers, the tail is replaced by a capacity-2 sampler
- Comparison-based - works on any ordered domain, no assumptions on value range or distribution
- Mergeable via the same merge-and-reduce structure - sketches of separate ingestions combine into one valid sketch

**Main findings**
- Proves a qualitative gap between randomized and deterministic quantile sketching (log log vs log dependence)
- All-quantiles version costs only a log(1/ε) factor more via union bound
- The analysis is "tight and extremely simple" - error is a zero-mean bounded-increment martingale over compaction rounds → sub-Gaussian tail

**Key takeaways**
- The rigorous alternative to t-digest for KGF's persisted score distributions: uniform-in-q additive error WITH a proof, at the cost of weaker tail resolution than t-digest's relative-error design
- For a gate threshold at the ~25th percentile (not extreme tail), KLL's uniform ε guarantee is adequate and auditable - a defensible choice when the calibration certificate itself is the product
- Practical sizing: ε = 0.01 needs a few hundred stored items regardless of how many ingestions accumulate - graph-node-sized state

**Tags**: #QuantileSketch #KLL #Streaming #OptimalSpace #Mergeable

**Source**: https://arxiv.org/abs/1603.05346. Local: [paper] KLL optimal quantile streams, 2016-03.pdf
