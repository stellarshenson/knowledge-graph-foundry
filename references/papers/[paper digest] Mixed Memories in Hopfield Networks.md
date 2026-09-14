**Mixed Memories in Hopfield Networks, Gayrard (CNRS / Aix-Marseille), 2026 (arXiv 2504.04879)**

The rigorous construction of the failure mode that kills superposition cues. For Hopfield models with activation function F on {-1,1}^N storing M random patterns, the paper explicitly constructs a class of **mixed memories** - configurations `ξ_i(m) = sign(Σ_μ m_μ ξ_i^μ)` formed from a finite mixture of the stored patterns - and proves they are genuine stable states of the energy, retrievable by the dynamics exactly as the real patterns are.

**Key mechanism**
- Mixed memories are sign-thresholded linear combinations of an odd number of patterns with deterministic mixture coefficients m
- They are constructed as solutions of the self-consistency equations, and shown stable with probability tending to one as N diverges
- The construction covers classical, dense and modern Hopfield activation functions

**Main findings**
- Storing patterns in the energy function **necessarily creates** unintended memories that overlap several patterns; their number is of order 3^M for M patterns
- Prior to this work the literature had only empirical/numerical understanding of these states; the paper makes them explicit for a general activation family
- Unlearning schemes and modified energies mitigate but do not eliminate them

**Key takeaways**
- **The direct null for any set-superposition cue**: the sum of several retrieved patterns is, by construction, in the basin of a mixed memory. One update from that cue returns the blend of what was already retrieved, not a new item
- Set-averaging and spuriousness are the same phenomenon seen from two sides - the metastable state that "represents a cluster" is a mixed memory
- Any mechanism that deliberately cues with a superposition must prove it escapes this basin, not assume it

**Tags**: #SpuriousStates #MixedMemories #Superposition #NullResult #R59

**Source**: https://arxiv.org/abs/2504.04879. Local: [paper] Mixed Memories in Hopfield Networks, 2025.pdf
