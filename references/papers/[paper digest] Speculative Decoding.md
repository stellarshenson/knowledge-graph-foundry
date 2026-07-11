# Speculative Decoding - Fast Inference from Transformers via Speculative Decoding

**arXiv 2211.17192 (ICML 2023, Google, Leviathan et al.)**. The draft-cheap / verify-exact execution paradigm: a small model speculatively generates several tokens, the large model verifies them in ONE parallel pass, and speculative sampling accepts/rejects so the output distribution is PROVABLY IDENTICAL to the large model alone. **2x-3x wall-clock speedup** on T5-XXL with no quality change and no retraining.

**Key mechanism**: acceptance rate alpha = E(beta), the expected fraction of draft tokens the verifier accepts, governs the entire economics: expected tokens per verifier pass is (1 - alpha^(gamma+1)) / (1 - alpha) for draft length gamma. Rejected speculation is discarded at the cost of the cheap draft only; the verifier's compute is amortized over accepted spans. Speculation pays exactly when draft cost << verify cost and alpha is high.

**Main findings**: even modest drafters (2 orders of magnitude smaller) achieve alpha 0.6-0.8 on real workloads; optimal gamma grows with alpha; the guarantee (identical distribution) means speculation is FREE in correctness terms - purely an economics trade.

**Key takeaways for KGF**: the clean formal frame for speculative graph construction economics - build cheap candidate structure eagerly (draft = kNN/link-prediction/heuristic edges, injected context fragments), verify lazily with the expensive instrument (LLM judge, resolver posterior, retrieval outcome), and let the acceptance rate decide whether speculation pays. The correctness contract transfers as doctrine: speculation must never change the committed distribution - a rejected speculative object must leave zero trace in trusted state.

**Tags**: speculative-execution, draft-verify, acceptance-rate, economics
**Source**: https://arxiv.org/abs/2211.17192 (PDF: `[paper] Speculative Decoding, 2022-11.pdf`)
