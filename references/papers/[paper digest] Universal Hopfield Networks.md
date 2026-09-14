**Universal Hopfield Networks: A General Framework for Single-Shot Associative Memory Models, Millidge, Salvatori, Song, Lukasiewicz, Bogacz (Oxford), ICML 2022 (arXiv 2202.04557)**

The decomposition paper. Every single-shot associative memory is `z = P · sep(sim(M, q))` - a **projection** matrix applied to a **separation** function applied to a **similarity** between the query and the stored-memory matrix. Classical Hopfield = dot product + identity separation (hence its poor capacity). Sparse Distributed Memory = Hamming distance + threshold (a **top-k**). Modern Hopfield / attention = dot product + softmax(β). Dense associative memory = dot product + polynomial of order n.

**Key mechanism**
- The triple is a one-hidden-layer feedforward network: separation is the hidden activation, projection is the output layer
- Separation controls capacity: identity gives linear, order-n polynomial gives **C ∝ N^(n-1)**, exponential/softmax gives exponential, max gives unbounded capacity in query dimension (but with vanishing basins of attraction)
- Similarity controls robustness: the axis along which corrupted cues are still recognised

**Main findings**
- Separation sweep (MNIST, CIFAR10, Tiny ImageNet; dot-product similarity held fixed): **exponential (softmax), max and 10th-order polynomial have substantially higher capacity**; low-order polynomials and identity collapse rapidly as stored count rises. Softmax at β=1 underperforms the 10th-order polynomial purely because β was pinned to 1 for fairness; as β→∞ softmax → max
- The value of a high-powered separation function **grows with data complexity** - more interference needs more numerical pushing-apart
- Similarity sweep: **Manhattan (l1) distance beats dot product**, equal on MNIST, slightly better on CIFAR10, substantially better on Tiny ImageNet; Euclidean also strong; KL, Jensen-Shannon and reverse KL substantially worse
- Dot product is robust to Gaussian noise; Manhattan is better under masking

**Key takeaways**
- The framework is explicitly **single-shot** (one forward pass). Iterative retrieval is named as a separate class and is not covered by the triple, so an iterated linear system such as personalized PageRank is not a UHN instance
- Top-k retrieval is a legitimate separation function (it is SDM's), so a dense top-k retriever already occupies the sharp end of the separation axis - the sweep's favourable direction (sharper) is where such a system already sits
- All empirical evidence is **image pixel-space reconstruction**, not text retrieval; external validity for embedding-space document retrieval is unestablished

**Tags**: #UniversalHopfield #Separation #Similarity #Projection #SDM #R59

**Source**: https://arxiv.org/abs/2202.04557. Local: [paper] Universal Hopfield Networks, 2022.pdf
