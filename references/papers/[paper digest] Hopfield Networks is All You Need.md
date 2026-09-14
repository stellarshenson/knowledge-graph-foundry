**Hopfield Networks is All You Need, Ramsauer, Schäfl, Lehner, Seidl, Widrich, Adler, Gruber, Holzleitner, Pavlović, Sandve, Greiff, Kreil, Kopp, Klambauer, Brandstetter, Hochreiter (JKU Linz), ICLR 2021 (arXiv 2008.02217)**

The paper that makes attention and associative memory the same object. A continuous-state modern Hopfield network stores **N ≥ √p · c^((d-1)/4)** random patterns on a sphere of radius M = K√(d-1) with failure probability p (proven for c ≥ 3.1546 at β=1, K=3, d=20, p=0.001), retrieves in **one update**, and has retrieval error **exponentially small in the pattern separation Δ_i**. The update rule `ξ_new = X softmax(β X^T ξ)` **is** transformer attention with β = 1/√d_k.

**Key mechanism**
- Separation of pattern i: **Δ_i := x_i^T x_i - max_{j≠i} x_i^T x_j** - the gap between a pattern's self-similarity and its nearest competitor
- Theorem 4/5: `‖f(ξ) - x_i‖ ≤ 2(N-1) M exp(-β(Δ_i - 2 max{‖ξ-x_i‖,‖x*_i-x_i‖} M))`, simplifying to `‖x_i - x*_i‖ ≤ 2e(N-1) M exp(-β Δ_i)` when cue and fixed point are both within 1/(2βM) of the pattern
- Three fixed-point regimes: (a) **global fixed point** = mean of all patterns (softmax near-uniform, no pattern separated); (b) **metastable state** = average over a cluster of mutually similar, jointly well-separated patterns; (c) **single-pattern fixed point** when Δ_i is large
- β is the single dial between the three regimes; the size of a metastable state is measured post hoc as **k = the minimal number of softmax entries summing to 0.90**, not predicted in closed form

**Main findings**
- Transformer and BERT attention heads sit predominantly in **metastable states**, classified into four bands by k (very large / large / medium / small); lower layers average globally, higher layers sharpen
- Hopfield layers improved state of the art on 3 of 4 multiple-instance-learning problems, on UCI small-table benchmarks, and on two drug-design datasets
- Capacity theorem is proved for **randomly chosen patterns on the sphere** - it does not transfer to correlated real embeddings; Theorems 4/5 do, since they depend only on the observed Δ_i, N, M, β

**Key takeaways**
- Any dense retrieval with a softmax over a fixed pattern matrix already **is** a one-step modern Hopfield retrieval; there is nothing extra to buy unless β, the similarity or the projection changes
- Δ_i is a **computable, per-pattern certificate**: required separation for error ε is Δ_i ≥ (1/β) ln(2(N-1)M/ε), growing only logarithmically in N - the honest scale-safety instrument
- Metastable states are named as the mechanism of set-averaging, but the paper offers **no principled β → target-set-size rule**; β is tuned and k is measured afterwards

**Tags**: #ModernHopfield #Attention #Separation #Capacity #Metastable #R59

**Source**: https://arxiv.org/abs/2008.02217. Local: [paper] Hopfield Networks is All You Need, 2020.pdf
