**Characteristic Functions on Graphs: Birds of a Feather, from Statistical Descriptors to Parametric Models (2020)**

The only paper in the awesome-graph-classification "Spectral and Statistical Fingerprints" chapter with a **node-level** mechanism rather than a whole-graph descriptor. FEATHER describes the *distribution* of node attributes in a neighbourhood using complex-valued characteristic functions (the Fourier transform of a probability distribution), weighted by r-step random-walk transition probabilities. Its explicit criticism of GNNs is that message passing computes only the **first moment** of the neighbourhood feature distribution, while a characteristic function evaluated at d points captures the whole distribution. Runs in **O(|E|·d·r)** time and **O(|V|·d)** memory - linear in graph size. Beats comparable unsupervised methods by up to **4.6%** AUC on node labelling and **12.0%** on graph classification.

**Key mechanism**
- Characteristic function of feature X at source node u, evaluation point θ: `E[e^{iθX}|G,u] = Σ_w P(w|u)·e^{iθx_w}`, where `P(w|u)` is an affiliation probability (tie strength) and u, w need NOT be adjacent
- The r-scale random-walk parametrization sets `P(w|u) = Âʳ_{u,w}` - the probability an r-step walk from u ends at w; Â is the normalized adjacency (D⁻¹A)
- Whole-graph matrix form: `Re(CF) = Âʳ · cos(x ⊗ Θ)` and `Im(CF) = Âʳ · sin(x ⊗ Θ)` for evaluation-point vector Θ ∈ ℝᵈ; two rows are similar iff the two nodes have similar feature distributions around them
- **Corruption bound (Theorem)**: corrupting one node w's feature by any ε changes u's descriptor by at most `2·Âʳ_{u,w}` - the damage from a bad neighbour is bounded by its random-walk weight, *regardless of the size of the corruption*
- Multi-feature extension iterates the same sparse propagation per feature and per scale, concatenating real and imaginary blocks
- Mean-pooling node characteristic functions yields a whole-graph descriptor that provably assigns isomorphic graphs the same representation - this pooled form is why the chapter files it as a "fingerprint"
- Parametric variants (FEATHER-L softmax, FEATHER-N neural) learn the evaluation points Θ end-to-end, reading the algorithm as the forward pass of a multi-scale GNN

**Main findings**
- Node classification on Wikipedia / Facebook / Deezer / Twitch / GitHub: up to **+4.6%** test AUC over comparable unsupervised attributed-embedding methods
- Graph classification: up to **+12.0%** test AUC
- Scales linearly with input size; robust to hyperparameter changes (evaluation-point count, scale r)
- Supervised variants beat the unsupervised model most strongly when the number of evaluation points is small
- Transfer learning across social networks works without retraining

**Key takeaways**
- Distinguishes two separable ideas that are usually conflated: the **pooling operator** (Âʳ-weighted neighbourhood aggregation of attributes) and the **descriptor** (characteristic function vs plain mean). The operator is generic; the characteristic function is the paper's novelty
- Tie-strength-bounded corruption is a formal robustness property that most neighbourhood-aggregation schemes lack, and it is stated per-node-pair rather than in aggregate
- A node's descriptor can carry information about nodes it is not adjacent to, without any query-time traversal

**Relevance**
- **The one transferable mechanism in the fingerprints chapter for KGF.** H582 established that the ~0.60 dense carrier-recall bound is embedder-invariant - swapping the *encoder* over the same indexed field does nothing - and concluded the opening "can only be closed by STRUCTURE". Neighbourhood pooling changes the indexed *field* rather than the encoder, which no hypothesis has tested
- The corruption bound is the direct answer to R10-H95's kill mechanism ("structural adjacency is anti-correlated with identity - a duplicate is the same entity extracted twice into different neighborhoods, so structure actively misleads"): a noisy neighbour's influence is capped by Âʳ_{u,w} rather than unbounded
- **Limitation for retrieval, recorded so the transfer is not overclaimed**: the characteristic-function transform maps nodes into a cos/sin feature space in which a text *query* has no image, breaking query-node comparability. Only the pooling operator (FEATHER's "first moment" - the baseline the paper improves upon) survives as a retrieval key. Tested as R54-H627
- The isomorphism-invariant pooled form is a whole-graph fingerprint and is fenced by H95 / H474 / H487, like the rest of the chapter

**Tags**
- #NodeEmbedding
- #NeighborhoodAggregation
- #CharacteristicFunctions
- #Robustness
- #GraphClassification

**Source**
- Download: https://arxiv.org/abs/2005.07959
- Local: [paper] FEATHER characteristic functions on graphs, 2020.pdf
