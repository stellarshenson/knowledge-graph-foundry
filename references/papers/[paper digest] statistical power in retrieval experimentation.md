**Statistical Power in Retrieval Experimentation (2008)**

Building directly on Sanderson and Zobel's 2005 topics-vs-depth result, Webber, Moffat and Zobel formalize the missing piece - not just whether a topic set is reliable, but how many topics an experiment needs to reliably *detect* a given effect size at all. They import statistical power analysis into IR evaluation, showing that estimating the required topic count from prior experience or a small trial run leaves wide margins of error, and that a set of nearly **150 topics** was necessary to reliably distinguish typical TREC-scale system pairs.

**Key mechanism**
- Statistical power framework applied to paired IR system comparisons: power is the probability of correctly detecting a true effect of a given size, as a function of sample size (topic count) and the variability of between-system score deltas
- Minimum Detectable Effect (MDE) / power-table method - for a target power level (e.g. 80%) and a measured or assumed variance, compute the topic count needed to detect a given score difference between two systems
- Empirically demonstrates that estimating the needed variance from past experience or from a small pilot trial produces wide, unreliable error margins on the resulting topic-count estimate
- Evaluates an alternative iterative strategy - keep adding topics until significance and power are both achieved - and shows this produces a systematic bias toward over-reporting significant findings
- Proposes a hybrid methodology combining power-informed topic-set sizing with explicit reporting requirements to counter that bias
- Extends Sanderson and Zobel's topics-vs-depth argument: a wide, shallow judgment pool across many topics beats a narrow, deep pool for reliability at fixed effort

**Main findings**
- A set of roughly **150 topics** was found necessary to reliably distinguish system pairs at typical TREC effect sizes and variance levels
- Variance estimates for the required-topic-count calculation, whether from prior experience or from a small trial, carry wide error margins - the same target power can imply very different topic counts depending on which estimate is trusted
- Iteratively growing the topic set until a test reaches significance biases results toward false positives - stopping rules matter as much as topic count
- Confirms and extends the Sanderson and Zobel (2005) conclusion that more topics with shallower judgment pools outperforms fewer topics with deeper pools

**Key takeaways**
- Topic count requirements are not a fixed constant - they depend on the effect size being chased and the underlying score-delta variance, and must be computed via a power table rather than assumed
- Ad hoc topic-set sizes (25, 50) chosen by convention rather than power calculation risk both false negatives (too few topics to detect a real difference) and, if iteratively grown without a stopping rule, false positives
- The MDE / power-table method is directly reusable: given KGF's measured variance in benchmark score deltas, it yields the topic count needed to trust a "run A beats run B" verdict at a chosen power level

**Relevance**
- Supplies the MDE / power-table method behind H540's band re-pricing - the ~150-topic figure is the empirical anchor for how many benchmark topics KGF needs to distinguish two ingestion/retrieval configurations reliably, not just avoid the known-unreliable 25-topic floor

**Tags**
- #StatisticalPower
- #IRatiEvaluation
- #TestCollections
- #ExperimentDesign

**Source**
- Download: https://codalism.com/research/papers/wmz08_cikm.pdf
- Local: [paper] statistical power in retrieval experimentation, 2008.pdf
