# [paper digest] How Do Neurons Operate on Sparse Distributed Representations? A Mathematical Theory of Sparsity, Neurons and Active Dendrites

**How Do Neurons Operate on Sparse Distributed Representations? A Mathematical Theory of Sparsity, Neurons and Active Dendrites** (Ahmad & Hawkins, Numenta, 2016; arXiv 1601.00720). A dendritic segment with as few as **20-30 synapses**, sampling a sparse population of **n=10,000** cells at **3% activity** (a=300 active), detects its target pattern with a false-positive rate of about **1 in 10^12** at threshold θ=12, and tolerates **20% corruption** (60 of 300 bits flipped) with a false-negative rate below **1 in 10^7**. At threshold θ=15 the same segment discriminates **1 million** random patterns with a false-positive rate better than 1 in a billion. The paper's central result for KGF is the union property: a single segment can absorb several independent patterns mixed (Boolean OR'd) onto its synapses and still recognize each one with negligible error, provided sparsity and dimensionality stay high.

## Key mechanism
- **Dendritic segment as coincidence detector** - a segment is a binary vector D over n potential presynaptic connections with s actual synapses (s=|D|); given presynaptic activity A, the segment spikes when match(A,D) = A·D >= θ, the NMDA spike threshold (Eq. 1)
- **Biological grounding** - experimentally, 8-20 spatially localized (20-300 micron), temporally synchronized (1-5ms) synapses trigger an NMDA spike that depolarizes the cell for 50-200ms; segments hold 20-300 synapses (Major et al., 2013) while n (potential connections) numbers in the thousands, so D is very sparse relative to n
- **Union property** - synapses recognizing different patterns are not cleanly segregated on a segment; a segment can instead hold the Boolean OR of s synapses from each of M patterns (X = union of x_i, Eq. 10) and still fire reliably on any stored pattern with up to s-θ bits of noise, with no false negatives - only a controlled rise in false positives as M grows
- **Population-level classification** - a set S of M independent segments (one pattern per segment, potentially on different cells) classifies input as a member if any segment matches (Eq. 7); the false-positive probability is bounded by P(A in S) <= M x P(match) (Eq. 9)

## Main findings
- n=10,000, s=30 synapses, 3% sparsity (a=300): θ=12 gives a false-positive rate of about 1 in 10^12; a 20% corruption of A (60 bits flipped, double the synapse count) gives a false-negative rate below 1 in 10^7
- n=10,000, 3% sparsity, s=30, θ=15: detects 1 million random SDR patterns with a false-positive rate better than 1 in a billion
- Error drops faster than exponentially as n increases, reaching essentially 0 once n > 2000; a dense (50% activity) representation cannot achieve robust recognition at any n
- A subsample of 20-25 synapses gives an error rate better than 10^-10, tolerant of noise up to 50% of the pattern (since θ = s/2 in that configuration)
- Union example: n=20,000, a=100 active cells, 25 synapses per pattern, θ=15, M=10 patterns unioned onto one segment - average synapse count on the segment stays under 250, false-positive rate stays below 1 in 10^11, and 98.75% of the union vector's bits remain zero
- Presynaptic population size drives union robustness: a population of 1,000 gives relatively high error when multiple patterns are stored; a population of 20,000 gives extremely low error even with 10 patterns stored on one segment
- Single dendritic segments observed experimentally to hold 100-400 synapses (Major et al., 2013) translate, via the theory, to 4-16 independently recognizable patterns per segment
- Predicted optimal NMDA spike threshold of 9-20 (diminishing returns above 15-20) matches the experimentally observed threshold range of 8-20 (Major et al., 2013; Branco & Häusser, 2011)

## Key takeaways
- Union property directly motivates R47-H503's node-bundle capacity knee: a sparse-coded bundle can have many patterns superimposed (mixed/OR'd) on it and each remains recognizable above an analytic false-positive threshold - the open question for KGF is where that knee sits as bundle occupancy (M) grows against dimensionality and threshold
- Subsampling result (20-30 synapses recognizing patterns drawn from thousands of cells) implies a bundle detector does not need dense connectivity or full pattern retention to recognize members reliably, provided sparsity and dimensionality are high
- Two closed-form knobs govern the capacity/error tradeoff at fixed sparsity and dimensionality: raising θ trades noise tolerance for a lower false-positive rate, while raising s or n drives error down faster than exponentially - both give KGF a scaling law rather than an empirical curve to size the knee against
- Eq. 4, 6, 9, and 15 provide closed-form false-positive/false-negative rates as functions of n, s, a, θ, and M, reusable for analytically sizing bundle capacity rather than sweeping it empirically

## Tags
`sparse-distributed-representation` `active-dendrites` `union-property` `numenta` `hawkins` `nmda-spike` `pattern-capacity` `subsampling`

## Source
- https://arxiv.org/abs/1601.00720 (PDF: https://arxiv.org/pdf/1601.00720)
