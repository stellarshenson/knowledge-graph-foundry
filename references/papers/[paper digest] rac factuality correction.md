**RAC: Efficient LLM Factuality Correction with Retrieval Augmentation**

RAC (Retrieval Augmented Correction) is a low-latency, single-pass post-correction method that lifts factuality by up to **30%** over prior state-of-the-art baselines on two popular factuality evaluation datasets, with no fine-tuning required and markedly lower latency than earlier iterative approaches.

Key mechanism:
- Decomposes an LLM's output into atomic facts
- Runs one fine-grained verify-and-correct pass against retrieved evidence per fact, rather than iterative re-generation of the whole response
- Model-agnostic - works with any instruction-tuned LLM, with or without an existing RAG pipeline

Main findings:
- Up to 30% improvement over state-of-the-art baselines across two factuality benchmarks
- Latency far below iterative self-correction methods since correction is single-pass, not multi-round
- Robust across different LLMs and both RAG and non-RAG settings

Key takeaways (relevance to KGF): validates a single-pass verify-then-revise pattern as a cost-efficient repair prior - decompose a claim into atomic facts, check each against retrieved evidence, and correct only the unsupported ones, instead of paying for iterative re-generation. Directly informs targeted narrow-question repair passes in the KGF repair queue (H578-adjacent), where per-fact correction keeps repair cost bounded as the graph scales.

Tags: factuality-correction, retrieval-augmented-generation, atomic-facts, single-pass-repair, low-latency

Source: https://arxiv.org/abs/2410.15667
