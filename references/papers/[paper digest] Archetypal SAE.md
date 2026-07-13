# Archetypal SAE: Adaptive and Stable Dictionary Learning for Concept Extraction in Large Vision Models

**Authors**: Thomas Fel, Ekdeep Singh Lubana, Jacob S. Prince, Matthew Kowal, Victor Boutin, Isabel Papadimitriou, Binxu Wang, Martin Wattenberg, Demba Ba, Talia Konkle (Harvard Kempner Institute, with FAR AI, CNRS, Google DeepMind)

**arXiv link (source for re-download)**: https://arxiv.org/abs/2502.12892

**Publication date**: 2025-02 (first arXiv version); ICML 2025 (PMLR 267)

## Summary

- Diagnoses a reproducibility failure in Sparse Autoencoders (SAEs): identical architectures retrained on the same data yield **divergent dictionaries** - measured stability (best-match cosine similarity across 4 reruns, Hungarian-aligned) is only **0.542 for TopK SAE** and **0.539 for JumpReLU SAE** on DINOv2 at 250M tokens/epoch, meaning roughly half the learned concepts have no counterpart in the next run
- Fix: **Archetypal SAE (A-SAE)** constrains every dictionary atom (decoder direction) to be a convex combination of the training data, D = WA with W row-stochastic, so D stays inside conv(A); the relaxed variant **RA-SAE** adds a small-norm deviation term Λ (||Λ||^2 <= δ) on top of a convex combination of K-means-reduced centroids C (32,000 centroids distilled from up to ~250M tokens), trading a controlled amount of hull constraint for reconstruction flexibility at scale
- On DINOv2 (2000-concept, 90%-sparse dictionary): RA-SAE reaches **stability 0.927** and **OOD score 0.060** while matching TopK's reconstruction (R2 89.34 vs 89.52) - classical methods are similarly stable (Semi-NMF 0.933, Convex-NMF 0.925) but reconstruct far worse (R2 55.48-67.43)
- Plausibility benchmark (alignment between learned atoms and a classifier's true class-direction weights): at dictionary size k=32k on ConvNeXt, TopK baseline plateaus at **0.1684** while A-SAE(δ=0) reaches **0.3999** and RA-SAE(δ=0.01) **0.4045**; on ResNet, TopK baseline spans 0.2295-0.3301 across k=512-32k vs A-SAE(δ=0) 0.5920-0.6133
- Soft Identifiability benchmark (recovering 4 collaged objects from 12 synthetic datasets): A-SAE scores **0.9482-0.9631** across DINOv2/ResNet/SigLIP/ViT, well above the best non-archetypal baseline (Semi-NMF 0.8297-0.8423, TopK SAE 0.8135-0.8328)

**Relevance to Knowledge Graph Foundry**: cited for R47-H504, the determinism gate requiring every sparse-coding component of the R47 GLiNER-adjacent pipeline to reproduce run-to-run. The paper's central finding is that unconstrained SAE dictionaries are not deterministic in practice - identical reruns on identical data diverge (stability 0.539-0.542 for TopK/JumpReLU), the exact failure mode H504 exists to rule out. Constraining dictionary atoms to the data's convex hull (A-SAE) or a mildly relaxed hull (RA-SAE) is an architecture-agnostic drop-in fix that lifts stability into the 0.925-0.933 range achieved by classical dictionary learning, without sacrificing reconstruction quality. If KGF adds a sparse dictionary layer alongside deterministic GLiNER extraction, this is the template: anchor atoms to convex combinations of the corpus's own embeddings rather than letting them float freely, and verify with the paper's Hungarian-aligned stability metric before trusting cross-run comparisons.

**Tags**: sparse-autoencoders, dictionary-learning, reproducibility, determinism, convex-hull, interpretability, archetypal-analysis
