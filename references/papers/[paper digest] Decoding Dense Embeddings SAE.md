**Decoding Dense Embeddings: Sparse Autoencoders for Interpreting and Discretizing Dense Retrieval, Park, Kim, Ko, 2025 (arXiv 2506.00041)**

A BatchTopK sparse autoencoder (SAE) decomposes a dense passage-retrieval embedding (SimLM, 768-dim) into a sparse set of human-interpretable latent concepts, then reuses those latents directly as an inverted-index retrieval unit - Concept-Level Sparse Retrieval (CL-SR). CL-SR (Efficient, k=32) matches SPLADE-max's MRR@10 (**0.343 vs 0.340** on MS MARCO Dev) at **0.11 FLOPs/query vs SPLADE's 1.35** - roughly 12x cheaper - while human annotators identify the source passage from its latent-concept description alone at **94.3%** accuracy.

**Key mechanism**
- BatchTopK SAE: encoder z(h) = sigma(Wenc*h + benc), decoder reconstructs h; the BatchTopK activation keeps only the top n*k activations across a batch of n samples, giving flexible per-sample sparsity k, plus an auxiliary loss to prevent dead latents
- Trained on ~8.8M MS MARCO passages and 0.5M train queries embedded by SimLM; latent dimension m = 32*d, sparsity k swept over {32, 48, 64, 128}
- CL-SR scores query-passage pairs with a BM25-style formula (Eq. 5) where latent activation values replace term frequency and an IDF-style weight downweights high-frequency, abstract latents; the inverted index is built from each passage's activated latents, capped at 24 (Efficient) / 65 (Max) latents per document
- Latent descriptions are generated once per latent: an LLM (GPT-4.1-mini) summarizes the top-30 MS MARCO passages that most activate each latent, producing a reusable natural-language label

**Main findings**
- Reconstruction/sparsity trade-off: NMSE drops from 0.1903 (k=32) to 0.1069 (k=128); reconstructed embeddings retain 80-90% of baseline SimLM MRR@10 and 98-99% of Recall@1k depending on k
- Latent intrusion test (9 activating + 1 random passage, LLM judge): accuracy falls from 0.859 (k=32) to 0.764 (k=128) - sparser codes are more monosemantic; the same test run on raw (non-SAE) 768-dim SimLM dimensions scores only 0.46, confirming the standard embedding basis is polysemantic by comparison
- Human interpretability: 94.3% accuracy identifying the source passage from latent descriptions alone (1-of-10 task); 90.3-93.8% accuracy simulating which of two passages SimLM would rank higher, given only latent descriptions and activation strengths
- CL-SR (Efficient) reaches MRR@10 0.343 / Recall@1k 0.954 at 0.11 FLOPs, 0.57GB index, 11,709-latent vocabulary; CL-SR (Max, k=128) reaches MRR@10 0.368 / Recall@1k 0.969 at 0.74 FLOPs, 1.27GB, 18,679-latent vocabulary - both match or beat SPLADE-max (MRR@10 0.340, 1.35 FLOPs, 2.60GB, 30,522-term vocab)
- Robustness on the 988 MS MARCO Dev queries where BM25 fails to retrieve the gold passage in top-1000: CL-SR Max holds MRR@10 0.143 (-61.1% vs its own top-1000-success rate) versus SPLADE-max 0.106 (-68.9%) and BM25 0.0 (-100%); dense SimLM itself drops to 0.185 (-55.0%)
- CPU search latency: CL-SR Efficient 117.96 ms/query versus dense SimLM 924.42 ms/query - roughly 8x faster; encode latency stays comparable across all methods (3.4-3.9 ms/query on GPU)

**Key takeaways**
- R47 relevance (H504/H508): CL-SR is a published, ablated recipe for turning dense embeddings into sparse, human-verifiable atoms at matched retrieval quality and a fraction of the FLOPs - direct precedent for KGF's sparse-code retrieval + identity line; the BatchTopK SAE plus IDF-weighted inverted-index scoring (Eq. 5) is a concrete mechanism to adopt or ablate against for H504/H508
- The k-vs-interpretability trade-off (intrusion-test accuracy falls as k rises) is a tunable knob, not a fixed constant - KGF's sparse-code identity work should treat sparsity level as a monosemanticity dial
- Latent descriptions are generated once (LLM summary of top-30 activating passages per latent) and reused across all downstream interpretation and scoring - a one-time labeling cost KGF's atom-verification step could mirror
- Authors flag SAE features as incomplete and dataset-dependent (citing Leask et al. 2025, Kissane et al. 2024) - any KGF sparse-code layer built this way inherits that caveat and needs its own completeness check

**Tags**: #SparseAutoencoder #ConceptLevelSparseRetrieval #Interpretability #DenseRetrieval #BatchTopK

**Source**: https://arxiv.org/abs/2506.00041. Local: [paper] Decoding Dense Embeddings SAE, 2025.pdf
