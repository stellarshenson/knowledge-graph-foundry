# Evaluating Design Decisions for Dual Encoder-based Entity Disambiguation

**arXiv 2505.11683 (2025), Rücker and Akbik.** Systematically ablates the design space of Dual Encoder entity disambiguation - loss function, similarity metric, label verbalization format, negative sampling strategy - producing **VerbalizED**, a document-level model that reaches **new state-of-the-art on the ZELDA benchmark**.

**Key mechanism**: mentions and label candidates are embedded into a shared space with a similarity metric predicting the correct label; the paper isolates each design axis (loss, similarity metric, verbalization, hard-negative sampling) and measures its individual contribution, then combines the winning choices with contextual label verbalizations and an iterative prediction variant for hard cases.

**Main findings**: contextual label verbalization and efficient hard negative sampling are the highest-impact design choices; the iterative prediction variant specifically improves disambiguation on the most challenging data points; comprehensive experiments on AIDA-Yago validate each component's individual contribution before combining them.

**Key takeaways for KGF**: serves as the ablation methodology template for the census feature-ablation - isolate each design axis independently (rather than only reporting the final combined system), report per-axis deltas, and reserve a separate "hard cases" analysis (their iterative variant) for the tail of difficult disambiguation decisions.

**Tags**: entity-disambiguation, dual-encoder, ablation-methodology, entity-linking
**Source**: https://arxiv.org/abs/2505.11683 (PDF: `[paper] dual encoder entity disambiguation ablation, 2025.pdf`)
