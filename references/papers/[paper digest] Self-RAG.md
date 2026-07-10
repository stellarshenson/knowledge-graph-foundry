**Self-RAG: Learning to Retrieve, Generate, and Critique through Self-Reflection, Asai, Wu, Wang, Sil, Hajishirzi, ICLR 2024 (arXiv 2310.11511)**

The trained-signal pole of adaptive retrieval. A single LM (**7B and 13B** variants) learns to emit special reflection tokens that decide, per segment, whether retrieval is needed and whether the generated segment is supported by the retrieved passages. The trained models outperform ChatGPT and retrieval-augmented Llama2-chat on open-domain QA, reasoning, and fact-verification tasks, with large gains in citation accuracy for long-form generation.

**Key mechanism**
- Four reflection token types: Retrieve (is retrieval needed now), IsRel (passage relevance), IsSup (is the output supported by the passage), IsUse (overall utility)
- A critic model (supervised on GPT-4-labeled examples) inserts reflection tokens into the training corpus offline; the generator is then trained with the plain LM objective - no critic hosted at inference
- At inference the generator emits Retrieve on demand, processes multiple passages in parallel, and ranks its own candidate segments by critique-token scores
- Token weights are tunable at inference - retrieval frequency and factuality/fluency trade-offs adjust without retraining

**Main findings**
- 7B/13B Self-RAG beats ChatGPT on PopQA, fact verification (PubHealth), and long-form citation precision
- On-demand retrieval beats both never-retrieve and always-retrieve baselines - indiscriminate augmentation hurts versatility
- Self-assessment tokens make generation controllable: hard constraints (only supported segments) enforceable at decode time

**Key takeaways**
- The sufficiency decision can live IN the generator as a trained signal - but requires training a critic + generator (heavy)
- Always-retrieve is measurably suboptimal even for factuality - the escalation-only-where-needed premise has trained-model evidence
- For KGF-H382 this is the expensive pole: the cheap alternative is an untrained self-report or an external threshold signal

**Tags**: #SelfRAG #AdaptiveRetrieval #ReflectionTokens #OnDemandRetrieval #ICLR

**Source**: https://arxiv.org/abs/2310.11511. Local: [paper] Self-RAG, 2023-10.pdf
