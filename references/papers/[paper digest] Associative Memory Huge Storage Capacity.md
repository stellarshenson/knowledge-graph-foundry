**On a Model of Associative Memory with Huge Storage Capacity, Demircigil, Heusel, Löwe, Upgang, Vermet, Journal of Statistical Physics 2017 (arXiv 1702.01929)**

The rigorous proof behind exponential capacity. Taking Krotov and Hopfield's polynomial interaction function to its limit - an **exponential** interaction `F(x) = exp(x)` - yields storage capacity **M = 2^(d/2)** in the number of neurons d, while the basins of attraction stay almost as large as in the standard Hopfield model.

**Key mechanism**
- Synaptic efficacy from the outer-product (Hebb) rule; the energy replaces the quadratic form with an exponential interaction, giving `E = -exp(lse(1, X^T ξ))`
- Retrieval with a single update recovers the fixed point with high probability for random patterns

**Main findings**
- Proves the Krotov-Hopfield claim that polynomial degree n raises capacity, then proves the exponential limit gives 2^(d/2) for binary patterns
- Basins of attraction do not collapse in the process, contrary to the naive expectation that sharper separation must shrink them
- The result is for **random binary patterns**; correlated pattern ensembles are outside the theorem

**Key takeaways**
- This is the theoretical warrant every "exponential capacity" claim in the modern Hopfield literature rests on, and it is a random-pattern result
- For real embeddings - which are strongly correlated - the exponential capacity number is not the operative bound; the separation-dependent retrieval-error bound is

**Tags**: #ExponentialCapacity #Demircigil #BinaryPatterns #R59

**Source**: https://arxiv.org/abs/1702.01929. Local: [paper] Associative Memory Huge Storage Capacity, 2017.pdf
