# R59 Hopfield / Associative-Memory Literature Grounding

**Executor**: research subagent, 2026-09-02T08:05:05Z. **Scope**: literature only - no experiments, no Neo4j, no canonical-doc writes.
**Papers filed**: 33 new PDFs + 33 digests in `references/papers/` (list at the end). Zero download failures; every PDF verified by `%PDF` magic header.

---

## Summary verdict table

| Id | Mechanism | Verdict | One-line reason |
|---|---|---|---|
| I1 | Universal Hopfield decomposition | do not register as a lever | The shipped dense@16 already **is** the (dot-product, top-k, identity) UHN instance; the separation axis is monotone toward sharpness and top-k already sits at the sharp end |
| I2 | Metastable states as a region rule | register with a narrowed claim | Reduces to adaptive-k (nucleus) dense seeding; the entire modern literature engineers metastability **away** rather than exploiting it |
| R1 | Region-cued associative completion | do not register | Formally identical to vector-based PRF at query-weight zero - the documented worst corner - and the superposition cue provably sits in the basin of a mixed memory |
| R2 | Iterated updates | do not register | Ramsauer Thm 4: when patterns are well separated the map is contractive and iteration is a no-op; when they are not, iteration converges to the blend |
| E1 | Hopfield identity pinning | register with a narrowed claim | The separation certificate is real and cheap, but on l2-normalised vectors it **is** one minus the nearest-competitor cosine - a margin, not a new quantity |
| E2 | Hebbian co-occurrence overlay | register, measurement-first | The only member of the family that writes edges, hence the only one that can cross components; strong published gains but a decisive inductive-transfer null |
| E3 | Stored question patterns | register | The only member that changes **what the dense channel matches against**, which is where the 0.26 bridge hit-rate lives |
| E4 | Capacity / interference forecast | register as a free instrument | The usable formula is the retrieval-error bound inverted, **not** the capacity theorem; shares all inputs with E1 |

---

## I1. UNIVERSAL HOPFIELD DECOMPOSITION

**MECHANISM**: Factor associative memories into (similarity, separation, projection); ask whether dense top-k, personalized PageRank and attention are all instances, and whether separation is an independently sweepable axis.

**PRIOR ART**: published.
- `[paper digest] Universal Hopfield Networks.md` - the triple `z = P · sep(sim(M, q))`. Classical Hopfield = dot product + **identity** separation. Sparse Distributed Memory = Hamming distance + **threshold**, i.e. a top-k. Modern Hopfield / attention = dot product + **softmax(beta)**. Dense associative memory = dot product + **order-n polynomial**.
- `[paper digest] Nonparametric Modern Hopfield Models.md` - constructs a **top-K modern Hopfield model** explicitly, with the same guarantees (attention connection, fixed-point convergence, exponential capacity). Dense top-k is therefore a member of the family by construction, not by analogy.
- `[paper digest] Attention Approximates Sparse Distributed Memory.md` - independent second reduction: attention's softmax approximates SDM's threshold read over the operative parameter range, pinning beta against the SDM read radius.
- `[paper digest] Equivalence Personalized PageRank Successor Representations.md` - **PPR is not in the triple.** Millidge (the UHN author) shows PPR and the successor representation are isomorphic, both being the stationary distribution of a random walk, i.e. the resolvent of a discounted transition operator. UHN is explicitly a framework for **single-shot** models; PPR is a fixed-point iteration over the graph transition operator, not the pattern matrix.

**MEASURED NUMBERS** (Millidge et al., ICML 2022, MNIST / CIFAR10 / Tiny ImageNet, image pixel reconstruction):
- Separation sweep with similarity held at dot product: **exponential (softmax), max and 10th-order polynomial have substantially higher capacity**; low-order polynomials and identity decline rapidly as stored count rises.
- Softmax underperforms the 10th-order polynomial **only because beta was pinned to 1** for a fair comparison; as beta approaches infinity softmax tends to max.
- The value of a high-powered separation function **grows with data complexity** - larger, more complex images cause more interference, which needs more numerical pushing-apart.
- Similarity sweep: **Manhattan (l1) beats dot product** - equal on MNIST, slightly better on CIFAR10, substantially better on Tiny ImageNet. Euclidean also strong. KL, Jensen-Shannon and reverse KL substantially worse. Dot product is the most robust to Gaussian noise; Manhattan is better under masking.
- `[paper digest] On Sparse Modern Hopfield Model.md` - the sparse (hard-zero) separation has a **provably tighter retrieval-error bound than the dense softmax analogue**.

**REDUCTION TEST**: reduces completely. The shipped `raw dense@16` is the UHN instance (dot-product similarity, top-16 threshold separation, identity projection). Formally: one modern Hopfield update is `xi' = X^T softmax(beta · X xi)`, which is one attention operation with queries=xi, keys=values=X and beta=1/sqrt(d_k); as beta grows it becomes argmax = top-1 dense retrieval, and a threshold separation gives top-k. The walk is **not** in the triple, per the PPR/SR note - so I1 cannot express the shipped pipeline as a whole, only its dense half.

**STRONGEST NULL**: every empirical separation result in the literature is **image pixel-space reconstruction**; there is no published separation sweep on text-embedding retrieval. And the axis is monotone toward sharpness (max > softmax(high beta) > softmax(beta=1) > low-order polynomial > identity), which is the direction a top-k retriever has already taken. There is no unexplored favourable direction.

**VERDICT**: **do not register as a lever.** Record the reduction as a one-page fact - it is load-bearing for adjudicating the other seven - and note that the literature's live axis is **similarity**, not separation (see MISSED MECHANISMS).

---

## I2. METASTABLE STATES AS A REGION RULE

**MECHANISM**: Use the moderate-beta regime deliberately, so one update returns the cluster-average of similar patterns rather than a single pattern - a set-valued region rule.

**PRIOR ART**: partially published - the regime is named and characterised, but nobody uses it deliberately for set retrieval, and there is no principled beta selection.
- `[paper digest] Hopfield Networks is All You Need.md` - three fixed-point regimes: global mean, metastable cluster-average, single pattern. Metastable-state size is measured **post hoc** as `k = the minimal number of softmax entries summing to 0.90`. There is **no closed-form beta -> target set size**; beta is tuned and k is measured afterwards.
- `[paper digest] Sparse and Structured Hopfield Networks.md` and `[paper digest] Hopfield-Fenchel-Young Networks.md` - the published, principled way to retrieve a **set** is **SparseMAP**, a structured sparse transformation whose support is an explicit combinatorial object. These same authors state plainly that the dense model "is incapable of exact retrieval and may require a low temperature to **avoid** metastable states (states which mix multiple input patterns)".
- `[paper digest] Modern Hopfield Networks Encoded Neural Representations.md` - metastable states are named as **"chief among"** the practical obstacles to large-scale content storage; the fix is raising separation upstream via a learned encoder.
- `[paper digest] Uniform Memory Retrieval Larger Capacity Hopfield.md` - U-Hop's entire contribution is a **separation loss that reduces metastable states**.

**MEASURED NUMBERS**:
- Transformer/BERT heads sit predominantly in metastable states, binned into four classes by k (Ramsauer et al.) - descriptive, not prescriptive.
- `[paper digest] Dynamic Manifold Hopfield Networks.md` - storing 2N patterns in N neurons, retrieval accuracy is **64% (context-modulated) vs 13% (modern Hopfield) vs 1% (classical)**. The flat modern model is already at 13% once stored count is twice the dimension.

**REDUCTION TEST**: reduces. A metastable state is the softmax-weighted average of a dense-score cluster; naming that cluster by thresholding cumulative softmax mass at 0.90 **is nucleus (top-p) selection over dense scores** - i.e. dense retrieval with adaptive k instead of fixed k=16. That is a one-parameter variant of the shipped seeder, not a new mechanism.

**STRONGEST NULL**: the whole modern literature is engineering metastability away (HEN, U-Hop, Hopfield-Fenchel-Young). Beyond that, the reduction shows the mechanism is adaptive-k dense seeding, and the bridge failure (dense hit-rate 0.26) is a property of the **embedding**, not of k - widening or adapting k cannot reach an entity the embedding does not rank.

**VERDICT**: **register with a narrowed claim** - a single cheap arm, "adaptive-k nucleus dense seeding (cumulative-mass 0.90) vs fixed dense@16", stated as a seeder variant and **not** as a Hopfield mechanism. Kill it if it does not beat 115/132 outright.

---

## R1. REGION-CUED ASSOCIATIVE COMPLETION

**MECHANISM**: Cue one Hopfield update with the sum/mean of the already-retrieved region's entity patterns, against the full pattern matrix, to harvest entities the question never named.

**PRIOR ART**: published - and published as a failure, twice, from two independent directions.
- `[paper digest] Mixed Memories in Hopfield Networks.md` (Gayrard) - rigorously constructs **mixed memories**, configurations `xi_i(m) = sign(sum_mu m_mu xi_i^mu)` formed from a mixture of stored patterns, and proves they are **stable states of the energy, retrievable by the dynamics exactly as the real patterns are**, with probability tending to one as N diverges. Their count is of order 3^M. Storing patterns necessarily creates them.
- `[paper digest] PRF Deep LMs Dense Retrievers Pitfalls.md` (already filed) - vector-based PRF **is this exact operation** in IR terms: average the query vector with feedback-passage vectors and re-score against the dense index. Its finding: dense vector PRF helps **only** when (i) the original query keeps the majority or equal weight and (ii) the feedback pool is shallow.

**THE FORMAL DISTINCTION FROM PRF - there is none that helps.** Vector PRF computes `alpha·q + (1-alpha)·mean(feedback)`. R1 sets **alpha = 0** and takes a deep pool (the whole region). That is the strictly more aggressive version of the exact configuration the campaign already killed at -1.6pp (fuse-add) and -2 flips (query-as-node). The only genuine differences are cosmetic to the algebra: the cue is assembled from graph-region entities rather than top-ranked passages, and the pattern bank holds entity prototypes rather than passages. Neither changes that the operation is one softmax-weighted average over a fixed bank with a mean-of-retrieved cue.

**MEASURED NUMBERS**: `[paper digest] Association Is Not Similarity Multi-Hop Retrieval.md` ablation - training the association function on **semantically similar but non-associated** passage pairs **degrades retrieval below the baseline**; shuffling association pairs causes severe degradation. Blending signals that are similar-but-not-associated is measured as actively harmful, not neutral.

**STRONGEST NULL**: Gayrard's mixed-memory theorem. The superposition of retrieved patterns is, by construction, in the basin of a spurious mixed memory. One update from that cue returns a blend of what was already retrieved. This is not a tuning risk - it is the model's proven stationary structure.

**VERDICT**: **do not register.** It is the alpha=0, deep-pool corner of a mechanism the campaign killed twice, and the associative-memory literature independently proves its cue lands on a spurious attractor.

---

## R2. ITERATED UPDATES

**MECHANISM**: Run the Hopfield update to a fixed point rather than once.

**PRIOR ART**: published, with a 2026 dynamical theory.
- `[paper digest] Dynamical Theory Sequential Retrieval Hopfield.md` (Betteti, Baggio, Zampieri) - the paper's own framing is that **sequential retrieval theory was previously absent**, supported only by numerical evidence. It derives, for a two-timescale input-driven-plasticity Hopfield network, explicit **gain thresholds** (the drive needed for a transition), **escape times** (dwell in one memory) and **collapse regimes**. The productive band between "nothing moves" and "trajectory degenerates" is narrow and parameter-dependent.
- `[paper digest] Hopfield Networks is All You Need.md` Theorem 4 - the update's Jacobian obeys `||J_m||_2 <= 2 beta N M^2 (N-1) exp(-beta(Delta_i - 2 max{...} M))`. For well-separated patterns this is a **contraction**, so one step lands epsilon-close to the fixed point and further steps move nothing.

**PUBLISHED EQUIVALENCE BETWEEN ITERATED HOPFIELD AND PRF QUERY EXPANSION**: none found. The nearest claim is a non-peer-reviewed blog note by Millidge ("Linear Attention as Iterated Hopfield Networks"), which is not filed as a paper. The defensible statement is structural, not a theorem: both are fixed-point iterations of "score -> average -> re-score" over a fixed bank, and both inherit the same dichotomy - contractive (iteration is a no-op) or non-contractive (iteration averages toward the blend).

**MEASURED NUMBERS**: none directly comparable. The campaign's own gated-second-walk result (+0) is consistent with the contraction reading.

**REDUCTION TEST**: reduces. In the well-separated regime it reduces to the one-step update the system already performs; in the badly-separated regime it reduces to I2's metastable/global average, i.e. drift.

**STRONGEST NULL**: Ramsauer Theorem 4 itself. Iteration is either a no-op or drift, with no published regime in between for retrieval; the one paper that maps the in-between regime (Betteti et al.) describes it as a narrow band between gain thresholds and collapse.

**VERDICT**: **do not register.** Already consistent with the killed gated-second-walk arm.

---

## E1. HOPFIELD IDENTITY PINNING

**MECHANISM**: Store canonical entity prototypes as the pattern matrix; each extracted mention is a cue; one-step retrieval either snaps it onto a prototype (merge) or leaves it separated (new entity), with the separation condition as the merge certificate.

**PRIOR ART**: partially published. Associative memory applied to **entity resolution, record linkage or coreference is essentially absent** from the literature. The three nearest items:
- `[paper digest] Hopfield Networks Meet Big Data Semantic Data Linking.md` - Hopfield memory for linking semantically related **attributes** across datasets, where the stored pattern is a **usage co-occurrence signature**, not the attribute's content. No comparison against standard entity-resolution baselines and no standard metrics; not usable as evidence that a Hopfield merge beats a cosine threshold.
- `[paper digest] Prototype Analysis Hopfield Hebbian Learning.md` - the theory of the object E1 wants. Hebbian learning over noisy examples of a prototype stabilises the **unlearned prototype itself**, and the authors derive a **stability condition** in the number of examples, the noise in them, and the number of non-example states, converted into a probability of stability.
- `[paper digest] Adaptive Hopfield Network Rethinking Similarities.md` - reframes the query as a **generative variant of a stored pattern** (literally the mention/canonical relation) and proves that no **fixed, pre-defined similarity** can rank variants by the likelihood of having generated the cue. Adaptive similarity is proved optimal for noisy, masked and biased variants.

**IS THE SEPARATION CONDITION USABLE AS A MERGE CERTIFICATE?** Yes, and it is cheap - but its content must be stated honestly.
- Definition: `Delta_i := x_i^T x_i - max_{j != i} x_i^T x_j`.
- Theorem 5: `||f(xi) - x_i|| <= 2 (N-1) M exp(-beta Delta_i)` (under `||x_i - x*_i|| <= 1/(2 beta M)` and `||x_i - xi|| <= 1/(2 beta M)`).
- Inverted, safe retrieval at error epsilon requires **`Delta_i >= (1/beta) ln(2 (N-1) M / epsilon)`**.
- **The honest reading**: with l2-normalised embeddings `x_i^T x_i = 1`, so `Delta_i = 1 - cos(i, nearest competitor)`. The certificate **is** one minus the nearest-competitor cosine. It is not an independent quantity from the cosine the hand-set threshold already uses.
- **What it nonetheless adds, and this is real**: (i) it is a **margin to the runner-up**, not an absolute level, so it fires on the ambiguous cases a global threshold cannot see; (ii) it makes the threshold an explicit function of **corpus size N and target error epsilon**, growing as `log N`, instead of a constant. That converts a hand-set constant into a principled, N-aware, per-entity adaptive threshold.

**KNOWN FAILURE MODES**:
- **Near-duplicate patterns**: `Delta -> 0` by construction. The certificate abstains precisely on the cases that matter, which is honest behaviour but not a merge decision.
- **Correlated patterns**: Prototype Analysis finds that at Bernoulli noise **p >= 0.3 prototype formation is disrupted** - the attractors selected are **very weak spurious states, not prototypes** - and that below the example threshold, adding more examples does not help. The campaign's 71%-extraction-variance regime is exactly this high-correlation, low-separation case.
- **Cue coverage**: the bound holds only for cues within `1/(2 beta M)` of the pattern. A mention far from every prototype gets no guarantee at all.
- **Metastability at scale**: `[paper digest] Modern Hopfield Networks Encoded Neural Representations.md` names metastable states as the chief practical obstacle for large, high-dimensional content stores.

**REDUCTION TEST**: **does not reduce to what is shipped** - the pattern bank is entity prototypes and the cue is a mention, an object the retrieval index does not hold. But it **does** reduce, on the decision itself, to a nearest-competitor cosine margin. Both statements must be carried together.

**STRONGEST NULL**: Prototype Analysis's disruption threshold. In a corpus where the dominant identity defect is surface-form variance, examples of the same entity are noisy and mutually disagreeing, which is the regime where the theory says you get weak spurious attractors rather than prototypes - and the certificate cannot tell the two apart, because both have small `Delta`.

**VERDICT**: **register with a narrowed claim** - "replace the constant cross-type cosine threshold with the nearest-competitor margin `Delta_i >= (1/beta) ln(2(N-1)M/epsilon)`, N-aware and per-entity", with U-Hop's separation loss held in reserve if the observed margin distribution is too tight to separate anything. The `Delta` distribution is computable today from an existing embedding dump, with no ingest.

---

## E2. HEBBIAN CO-OCCURRENCE OVERLAY

**MECHANISM**: Build `W = sum of outer products` over chunk-local entity sets, threshold it, and write the surviving pairs as real edges at ingest.

**PRIOR ART**: published, with strong recent gains **and** a decisive transfer null.
- `[paper digest] Predictive Associative Memory Temporal Co-occurrence.md` - the framework. Association weight is co-occurrence **minus a familiarity baseline**: `w_assoc = w_raw - E[w_raw]`; only co-occurrence in excess of expectation counts.
- `[paper digest] Association Is Not Similarity Multi-Hop Retrieval.md` - the applied test on real multi-hop QA.
- `[paper digest] SiReRAG Similar and Related Multihop.md` - independent confirmation that an entity-relatedness index complements a similarity index on exactly the 2WikiMultiHopQA family.
- `[paper digest] Simplicial Hopfield Networks.md` - the materialisation-budget result.

**MEASURED NUMBERS**:
- PAM (synthetic navigation benchmark): Association Precision@1 = **0.970**; **cross-boundary Recall@20 = 0.421 where cosine similarity scores exactly zero**; discrimination AUC **0.916 vs cosine 0.789**, and on cross-room pairs where embedding similarity is uninformative **0.849 vs cosine 0.503 (chance)**. Temporal-shuffle control collapses cross-boundary recall by **90%**, proving the signal is co-occurrence structure and not embedding geometry.
- AAR (real): HotpotQA passage **Recall@5 0.831 -> 0.916 (+8.6 points)**, with **+28.5 points on hard questions where the dense baseline fails**; MuSiQue **+10.1**; downstream **+6.4 exact match**; 3.7 ms per query, under two minutes of training.
- SiReRAG: roughly **+1.9 average F1** over the strongest prior indexing method on MuSiQue / 2WikiMultiHopQA / HotpotQA - the realistic size of a whole extra index on this benchmark family.
- Simplicial Hopfield: **a small random subset of setwise connections, of size equal to the all-pairwise network, still outperforms the pairwise network** - which connections you keep dominates how many.

**REDUCTION TEST**: **does not reduce.** PAM's cosine-scores-zero result is a direct demonstration that association is not recoverable from similarity. Nor does it reduce to the shipped full 1-hop shell: the edges it adds are exactly the chunk-local entity pairs the extractor did **not** relate. This is **the only mechanism in the eight that writes adjacency**, and therefore the only one not bound by the block-diagonality of `f(A_hat)`.

**STRONGEST NULL**: AAR's inductive result. The **inductive variant - trained on training-split associations, evaluated on unseen associations - shows no significant improvement.** The transductive gain came from co-occurrence **as supporting facts for questions**, which is question supervision, not generic textual co-occurrence. Compounding this, training on **semantically similar but non-associated** pairs degrades retrieval **below baseline**. Separately, the campaign's own residual analysis caps the ceiling hard: of 33 retrieval misses, **12 golds are absent from the graph entirely** and no edge can retrieve a node that does not exist; the addressable cross-component share is 4 (+2 deep-in-both).

**VERDICT**: **register, measurement-first.** Gate the write behind two free graph queries: (1) how many chunk-local co-occurring entity pairs are not already adjacent, and (2) how many of those cross a component boundary. Only if (2) is non-trivial, write **baseline-subtracted or PMI-filtered** edges - and prefer setwise/hyperedge encoding of the chunk's entity set over pairwise expansion, per Simplicial Hopfield. Expected ceiling on this rung is small (~4-6 of 132); the mechanism's real value is structural, for the next rung.

---

## E3. STORED QUESTION PATTERNS

**MECHANISM**: Generate answerable questions per chunk at ingest, store them as memory patterns, cue with the user query, project back to the source chunk.

**PRIOR ART**: fully published; most of it was already filed before this round.
- Already filed: `[paper digest] QuOTE.md`, `[paper digest] doc2query.md`, `[paper digest] Doc2Query--.md`, `[paper digest] QA-Expand.md`, `[paper digest] HyDE Zero-Shot Dense Retrieval.md`.
- Newly filed: `[paper digest] Doc2Query++ Topic-Coverage Expansion.md` - the interference curve.

**MEASURED NUMBERS**:
- QuOTE: SQuAD top-1 context accuracy **67.11% -> 77.65% (+10.5)**; Natural Questions **32.92% -> 38.00% (+5.1)**; MultiHop-RAG full-match@20 **22.50% -> 35.00% (+12.5)**. Best at **~10 questions per chunk** (5-20 usable, diminishing past 10-15). Indexing cost ~16x, one-time; query latency 141 ms vs HyDE's 1,274 ms.
- doc2query: MS MARCO MRR@10 **18.4 -> 21.5**, Recall@1000 **85.3% -> 89.3%**. docTTTTTquery at 40 queries/passage: MRR@10 **27.2** (5 samples 25.9, 10 samples 26.5, 20 samples 27.2 - monotone but diminishing).
- Doc2Query--: relevance-filtering the generated queries gives **up to +16% effectiveness, -33% index size, -23% query time**. Hallucinated generated queries actively harm retrieval.
- Doc2Query++: scaling 0 to 600 generated queries per document on FiQA-2018, sparse retrieval, **performance peaks around 100 and degrades afterwards**. Separately, **appending generated queries to passage text harms dense retrieval**; the fix is Dual-Index Fusion, keeping text and query signals in separate indices.

**IS ANYONE FRAMING THIS AS ASSOCIATIVE MEMORY WITH A CAPACITY BOUND?** **No.** The IR literature and the Hopfield literature do not connect here. The nearest available frame is `[paper digest] Modern Hopfield Networks Encoded Neural Representations.md`, which does hetero-association (retrieve an image from a natural-language query) through a learned encoder and identifies metastable states as the scaling obstacle. Under that frame, "questions per chunk" is a stored-pattern count and the interference the IR papers measure empirically at ~10 (QuOTE) and ~100 (Doc2Query++) is the capacity-and-separation story the Hopfield theory would predict. The frame is available and unclaimed - it would be a genuine contribution, but it is a paper, not a lever.

**REDUCTION TEST**: reduces to dense retrieval **with a different index content**. It changes what is embedded, not the retrieval operator. That is exactly why it is the interesting one: the bridge failure is that bridges are absent from the question text while their chunks are declarative, and a question-form index changes the surface the cue matches against - the one thing no separation, temperature or walk change can do.

**STRONGEST NULL**: three, stacked. (i) Doc2Query++'s explicit finding that **concatenating generated queries into passages harms dense retrieval** - the naive implementation is a documented regression. (ii) The headline gains are single-hop (SQuAD, NQ, MS MARCO); QuOTE's own multi-hop absolute numbers stay modest despite large relative gains. (iii) Structurally: questions generated **from** a chunk describe that chunk, so a bridge entity absent from the chunk's own text will not appear in its questions - the mechanism helps first-hop and terminal matching more than it helps bridges.

**VERDICT**: **register.** Narrow to: a **separate question index with fusion** (never concatenation), **~10 questions per chunk**, **relevance-filtered** per Doc2Query--. It is the only candidate that attacks the representation the 0.26 bridge hit-rate lives in.

---

## E4. CAPACITY / INTERFERENCE FORECAST

**MECHANISM**: Given N stored patterns of dimension d and an observed similarity distribution, forecast the N at which retrieval errors begin - a scale-safety instrument for the 6,118-document rung.

**PRIOR ART**: published, but **the usable formula is not the capacity theorem**.
- `[paper digest] Hopfield Networks is All You Need.md` Theorem 3: `N >= sqrt(p) · c^((d-1)/4)`, proven for c >= 3.1546 at beta=1, K=3, d=20, p=0.001. This is for **randomly chosen patterns on a sphere** and does not transfer to correlated text embeddings.
- `[paper digest] Associative Memory Huge Storage Capacity.md`: `2^(d/2)`, for **random binary patterns**. Same limitation.
- `[paper digest] Exponential Capacity Dense Associative Memories.md` (Lucibello and Mezard): exact asymptotic threshold `alpha_1` for retrieving a **typical** pattern and lower bounds on `alpha_c` for retrieving **all** patterns, plus basin sizes. Crucially, Gaussian and spherical pattern ensembles give **rich and qualitatively different phase diagrams** - the capacity constant is distribution-dependent, so there is no universal N.

**THE USABLE INSTRUMENT** is Ramsauer Theorem 5 inverted, which is **distribution-free in the patterns** because it depends only on observables:

> Required separation at corpus size N and target retrieval error epsilon: **`Delta_required(N, epsilon) = (1/beta) · ln( 2 (N-1) M / epsilon )`**

Scaling the stored count by a factor r raises the requirement by only `(1/beta) ln r`. Medium to large is roughly 132 to 6,118 documents; if the entity count scales similarly (~46x), the requirement rises by `ln(46)/beta ~= 3.83/beta`. Measure the current empirical `Delta_i` distribution over entity prototypes, shift the requirement by `ln(r)/beta`, and read off **the percentile of prototypes that fall below the certificate at the new N**. All inputs are shared with E1; it is one nearest-neighbour lookup per prototype over an existing embedding dump.

**MEASURED NUMBERS** as empirical anchors: `[paper digest] Dynamic Manifold Hopfield Networks.md` reports **13% retrieval accuracy for modern Hopfield when storing 2N patterns in N neurons** (1% classical, 64% context-modulated). The practical cliff sits far below the theoretical exponential capacity.

**REDUCTION TEST**: not a retrieval mechanism at all - it is an instrument. It does not compete with anything shipped.

**STRONGEST NULL**: the forecast assumes the **shape** of the `Delta` distribution is stable under scaling. New documents add near-duplicate entities, which pushes the left tail down faster than `log N` pushes the requirement up. The forecast is therefore a **lower bound on the damage**, not a prediction. Also: no capacity work in this literature is on text embeddings.

**VERDICT**: **register as a free instrument, not an experiment.** State the `log N` requirement, the observed `Delta` percentile curve, and the projected percentile that fails at the large rung. Label it a lower bound.

---

## MISSED MECHANISMS

Six mechanisms in this literature bear on the campaign and were not on the list.

1. **Learned similarity, not learned separation.** `[paper digest] Adaptive Hopfield Network Rethinking Similarities.md` proves that no fixed similarity can rank generative variants of a stored pattern by the likelihood of having produced the cue, and learns the likelihood instead; `[paper digest] Universal Hopfield Networks.md` finds Manhattan beats dot product with the gap **growing with data complexity**; `[paper digest] Uniform Memory Retrieval Larger Capacity Hopfield.md` (U-Hop) makes separation **trainable** via a separation loss in a learned kernel space. The literature's own verdict is that the similarity axis is where the remaining headroom is - directly serving E1 and E4 rather than the retrieval side.

2. **Structured set retrieval via SparseMAP.** `[paper digest] Sparse and Structured Hopfield Networks.md` retrieves **pattern associations** with an explicit, jointly-selected support. This is what I2 actually wants, done principledly - a controlled support rather than a tuned temperature - and it is not reproducible by any top-k or beta setting.

3. **Setwise (simplicial) connections.** `[paper digest] Simplicial Hopfield Networks.md`: a **small random subset** of setwise connections outperforms an all-pairwise network of the same size. For E2 this says two things - encode a chunk's entity set as a hyperedge rather than decomposing it into pairs, and expect selectivity to matter more than volume.

4. **Daydreaming / spurious-state erasure.** `[paper digest] Daydreaming Hopfield Networks.md` alternates Hebbian reinforcement with non-destructive erasure of the spurious attractors the dynamics reach on their own. On **correlated** data it turns correlation into a capacity gain, and on MNIST it produces attractors close to **class prototypes**. This is the only published method that makes the extraction-variance regime work in favour of prototype formation instead of against it - the natural companion to E1.

5. **Hierarchical associative memory.** `[paper digest] Hierarchical Associative Memory.md` assembles a retrieved memory from lower-layer primitives under higher-layer assembly rules. It is the principled alternative to R1: composition through layered assembly, not through superposition cueing.

6. **Hetero-associative encoding.** `[paper digest] Modern Hopfield Networks Encoded Neural Representations.md` - cue in one space, retrieve in another, with a learned encoder raising separation. This is the formal frame for E3 and the published fix for the metastability that limits every large pattern bank.

---

## THE REDUCTION, STATED PRECISELY

**Is "modern Hopfield retrieval = attention = dense retrieval with a temperature knob" correct?** Yes, under a stated condition.

For a fixed pattern matrix `X` whose rows are the stored vectors, one modern Hopfield update is

> `xi' = X^T softmax(beta · X xi)`

This is simultaneously (i) exactly one attention operation with queries `xi`, keys and values `X`, and `beta = 1/sqrt(d_k)` (Ramsauer et al.); (ii) exactly the Universal Hopfield triple with dot-product similarity, softmax separation and `X`-projection (Millidge et al.); (iii) as `beta -> infinity`, argmax, i.e. top-1 dense retrieval - and with a threshold separation instead, top-k dense retrieval, which is Sparse Distributed Memory's slot in the triple (Bricken and Pehlevan) and is constructed explicitly as the **top-K modern Hopfield model** by Hu et al.

**A Hopfield formulation is NOT reducible to the shipped stack under exactly four conditions:**

1. **The pattern matrix is not the retrieval index.** If patterns are entity prototypes and cues are mentions (E1), or patterns are generated questions and cues are user queries (E3), the Hopfield reading supplies an error bound and a separation certificate over an object the dense retriever does not index. This is a genuine gain in **analysis**; the retrieval operation is still a nearest-neighbour lookup.

2. **The update is iterated with the output re-entering the cue.** Then it is a dynamical system with its own convergence conditions (Betteti et al.), not a single retrieval. But note the sting: Ramsauer Theorem 4 shows the map is a **contraction** when patterns are well separated, so this non-reducibility is real only in the badly-separated regime - where the fixed point is a blend.

3. **The separation is structured rather than pointwise.** SparseMAP selects a support jointly; no temperature or k reproduces it.

4. **The outer-product weight matrix is used as a graph.** Writing `W`'s surviving entries as **edges** changes the adjacency the walk runs on. This is the single place the family escapes dense retrieval entirely, and the only one that can cross component boundaries - because every analytic `f(A_hat)` is block-diagonal, but `A_hat` itself is not fixed.

Everything else proposed in R59 - R1, R2, and I2 as drafted - is a re-parameterisation of the shipped `dense@16 + anchor-reset walk`.

---

## PAPERS FILED

33 new PDFs and 33 new digests in `references/papers/`. Every PDF verified by `%PDF` magic header. Digest filenames drop the year, per project convention.

**Core theory**
1. `[paper] Hopfield Networks is All You Need, 2020.pdf` / `[paper digest] Hopfield Networks is All You Need.md`
2. `[paper] Universal Hopfield Networks, 2022.pdf` / `[paper digest] Universal Hopfield Networks.md`
3. `[paper] Dense Associative Memory for Pattern Recognition, 2016.pdf` / `[paper digest] Dense Associative Memory for Pattern Recognition.md`
4. `[paper] Associative Memory Huge Storage Capacity, 2017.pdf` / `[paper digest] Associative Memory Huge Storage Capacity.md`
5. `[paper] Large Associative Memory Problem, 2020.pdf` / `[paper digest] Large Associative Memory Problem.md`
6. `[paper] Hierarchical Associative Memory, 2021.pdf` / `[paper digest] Hierarchical Associative Memory.md`
7. `[paper] Attention Approximates Sparse Distributed Memory, 2021.pdf` / `[paper digest] Attention Approximates Sparse Distributed Memory.md`

**Separation, sparsity, structured retrieval**
8. `[paper] On Sparse Modern Hopfield Model, 2023.pdf` / `[paper digest] On Sparse Modern Hopfield Model.md`
9. `[paper] Sparse and Structured Hopfield Networks, 2024.pdf` / `[paper digest] Sparse and Structured Hopfield Networks.md`
10. `[paper] Hopfield-Fenchel-Young Networks, 2024.pdf` / `[paper digest] Hopfield-Fenchel-Young Networks.md`
11. `[paper] Nonparametric Modern Hopfield Models, 2024.pdf` / `[paper digest] Nonparametric Modern Hopfield Models.md`
12. `[paper] STanHop Sparse Tandem Hopfield, 2023.pdf` / `[paper digest] STanHop Sparse Tandem Hopfield.md`
13. `[paper] Simplicial Hopfield Networks, 2023.pdf` / `[paper digest] Simplicial Hopfield Networks.md`

**Capacity, separation as an instrument, metastability**
14. `[paper] Exponential Capacity Dense Associative Memories, 2023.pdf` / `[paper digest] Exponential Capacity Dense Associative Memories.md`
15. `[paper] Uniform Memory Retrieval Larger Capacity Hopfield, 2024.pdf` / `[paper digest] Uniform Memory Retrieval Larger Capacity Hopfield.md`
16. `[paper] Modern Hopfield Networks Encoded Neural Representations, 2024.pdf` / `[paper digest] Modern Hopfield Networks Encoded Neural Representations.md`
17. `[paper] Dynamic Manifold Hopfield Networks, 2026.pdf` / `[paper digest] Dynamic Manifold Hopfield Networks.md`
18. `[paper] Adaptive Hopfield Network Rethinking Similarities, 2025.pdf` / `[paper digest] Adaptive Hopfield Network Rethinking Similarities.md`

**Spurious states, iteration, prototypes**
19. `[paper] Mixed Memories in Hopfield Networks, 2025.pdf` / `[paper digest] Mixed Memories in Hopfield Networks.md`
20. `[paper] Daydreaming Hopfield Networks, 2024.pdf` / `[paper digest] Daydreaming Hopfield Networks.md`
21. `[paper] Dynamical Theory Sequential Retrieval Hopfield, 2026.pdf` / `[paper digest] Dynamical Theory Sequential Retrieval Hopfield.md`
22. `[paper] Prototype Analysis Hopfield Hebbian Learning, 2024.pdf` / `[paper digest] Prototype Analysis Hopfield Hebbian Learning.md`

**Applied results and null results**
23. `[paper] Modern Hopfield Networks Immune Repertoire, 2020.pdf` / `[paper digest] Modern Hopfield Networks Immune Repertoire.md`
24. `[paper] CLOOB InfoLOOB Modern Hopfield, 2021.pdf` / `[paper digest] CLOOB InfoLOOB Modern Hopfield.md`
25. `[paper] Hopular Tabular Modern Hopfield, 2022.pdf` / `[paper digest] Hopular Tabular Modern Hopfield.md`
26. `[paper] Energy Transformer, 2023.pdf` / `[paper digest] Energy Transformer.md`
27. `[paper] Graph Hopfield Networks Node Classification, 2026.pdf` / `[paper digest] Graph Hopfield Networks Node Classification.md`
28. `[paper] Hopfield Networks Meet Big Data Semantic Data Linking, 2025.pdf` / `[paper digest] Hopfield Networks Meet Big Data Semantic Data Linking.md`

**Association, co-occurrence, retrieval**
29. `[paper] Predictive Associative Memory Temporal Co-occurrence, 2026.pdf` / `[paper digest] Predictive Associative Memory Temporal Co-occurrence.md`
30. `[paper] Association Is Not Similarity Multi-Hop Retrieval, 2026.pdf` / `[paper digest] Association Is Not Similarity Multi-Hop Retrieval.md`
31. `[paper] SiReRAG Similar and Related Multihop, 2024.pdf` / `[paper digest] SiReRAG Similar and Related Multihop.md`
32. `[paper] Equivalence Personalized PageRank Successor Representations, 2025.pdf` / `[paper digest] Equivalence Personalized PageRank Successor Representations.md`
33. `[paper] Doc2Query++ Topic-Coverage Expansion, 2025.pdf` / `[paper digest] Doc2Query++ Topic-Coverage Expansion.md`

**Already filed before this round, cited above**: `[paper digest] QuOTE.md`, `[paper digest] doc2query.md`, `[paper digest] Doc2Query--.md`, `[paper digest] QA-Expand.md`, `[paper digest] HyDE Zero-Shot Dense Retrieval.md`, `[paper digest] PRF Deep LMs Dense Retrievers Pitfalls.md`, `[paper digest] LLM-Assisted Pseudo-Relevance Feedback.md`, `[paper digest] HippoRAG.md`, `[paper digest] HippoRAG 2.md`.
