**A Simple Yet Effective Baseline for Non-Attributed Graph Classification (2019)**

A methodological reality check on the graph-classification literature. The authors build the **Local Degree Profile** - a representation using nothing but each node's degree and the degrees of its immediate neighbours - and show it matches state-of-the-art graph kernels and graph neural networks on non-attributed graph classification. Linear-time to compute. The argument is that as methods grow more sophisticated, the field needs to know which components actually carry the performance.

**Key mechanism**
- For each node v, five numbers: `deg(v)`, and the min / max / mean / standard deviation of `{deg(u) : u ∈ N(v)}`
- Each of the five is summarised across the graph by an empirical histogram; concatenating the histograms gives the graph feature vector
- Feed to a standard classifier; no learning of the representation at all
- The paper draws the explicit connection to GNNs: one message-passing layer over degree features computes essentially these aggregates, so LDP is a one-layer GNN with hand-picked pooling

**Main findings**
- Matches state-of-the-art kernels and GNNs on a range of non-attributed graph-classification benchmarks
- Slightly weaker on attributed graphs, which it does not use attributes for - the honest scope limit
- Efficient (linear-time) and trivially reproducible

**Key takeaways**
- Benchmark performance in graph classification is frequently attributable to degree statistics rather than to any sophisticated structural modelling - a strong prior to hold when a structural method reports a win
- The value of the paper is as a **mandatory control**, not as a method - which is precisely how KGF's own H556 honest-control doctrine treats trivial baselines

**Relevance**
- **Doctrinal rather than mechanical relevance.** The LDP feature set is the same cheap-structural-feature family that R45-H545, H556, H573 and R10-H100 already killed on our substrate: structural features collapse to seed-hop distance and do not predict probe fate
- Its real transfer to KGF is the methodological point we already run as doctrine - R52-H598's finding that a trivial hop control (0.926) beat every diffusion arm is exactly this paper's lesson reproduced on our own graph
- Cited as the reference for why every KGF structural hypothesis must carry a degree/hop control before it may claim a win

**Tags**
- #Baseline
- #GraphClassification
- #DegreeFeatures
- #Methodology

**Source**
- Download: https://arxiv.org/abs/1811.03508
- Local: [paper] LDP local degree profile baseline, 2019.pdf
