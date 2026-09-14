**Dense Associative Memory for Pattern Recognition, Krotov, Hopfield (IAS / Princeton), NeurIPS 2016 (arXiv 1606.01164)**

The paper that broke the linear capacity ceiling. Replacing the quadratic Hopfield energy with an interaction function `F(x) = x^n` raises storage capacity from ~0.14d to **proportional to d^(n-1)**, and establishes a duality between dense associative memory and one-hidden-layer feedforward networks whose activation is the interaction function's derivative (rectified polynomials of degree n).

**Key mechanism**
- Energy `E = -Σ_μ F(ξ_μ^T σ)` with F a rectified polynomial of order n; n = 2 recovers the classical Hopfield network
- The family interpolates between a **feature-matching regime** (small n: many patterns each contribute, retrieval is a weighted blend of features) and a **prototype regime** (large n: one pattern dominates, retrieval snaps to a single stored item)
- Duality: the associative-memory update equals a forward pass through a hidden layer with rectified-polynomial activation

**Main findings**
- Capacity scales as d^(n-1); higher n buys capacity at the cost of narrower basins of attraction
- Demonstrated on XOR and MNIST; higher rectified polynomials work as deep-learning activations
- The **feature-to-prototype transition is controlled by the exponent alone** - the same knob that in the modern continuous model becomes β

**Key takeaways**
- Prototype regime is the regime in which "snap this mention onto its canonical entity" is even well posed; feature regime returns blends
- Capacity growth is bought entirely by sharper separation, and sharper separation shrinks the basin - the two cannot be maximised together
- Capacity results assume random uncorrelated patterns; correlated data is out of scope here and is where the model degrades

**Tags**: #DenseAssociativeMemory #Krotov #Capacity #PrototypeRegime #R59

**Source**: https://arxiv.org/abs/1606.01164. Local: [paper] Dense Associative Memory for Pattern Recognition, 2016.pdf
