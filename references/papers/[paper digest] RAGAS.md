# RAGAS: Automated Evaluation of Retrieval Augmented Generation

**Authors**: Shahul Es, Jithin James, Luis Espinosa-Anke, Steven Schockaert (Exploding Gradients, Cardiff NLP, AMPLYFI)

**arXiv link (source for re-download)**: https://arxiv.org/abs/2309.15217

**Publication date**: 2023-09-26

## Summary

- Reference-free RAG evaluation: three continuous 0-1 metrics computed by LLM prompting, no gold answers needed - **faithfulness** (decompose answer into statements, verify each against retrieved context, score = supported/total), **answer relevance** (generate n questions from the answer, mean cosine similarity to the original question), **context relevance** (extracted-relevant-sentences / total context sentences)
- WikiEval validation set: 50 post-2022 Wikipedia pages, pairwise human preferences; two annotators agree **~95%** on faithfulness and context relevance, **~90%** on answer relevance - the human ceiling for these judgments
- Agreement with human preference (accuracy): faithfulness **0.95**, answer relevance **0.78**, context relevance **0.70**
- Baselines collapse: direct GPT scoring 0-10 gets 0.72/0.52/0.63; GPT pairwise ranking 0.54/0.40/0.52 - the decomposed-metric construction, not the LLM, carries the signal
- Context relevance is the weakest instrument (0.70 = 30% disagreement with humans) - the LLM struggles to select relevant sentences from long contexts

**Relevance to Knowledge Graph Foundry**: the canonical reference-free continuous metric pattern - statement-level decomposition converts a binary judgment into a ratio, exactly the move KGF needs to escape binary probes. But the agreement numbers ARE the noise floor: a faithfulness instrument that disagrees with humans 5% of the time cannot certify deltas below ~5 points without rectification (see PPI/ARES digests). Context relevance at 0.70 is too noisy to gate anything.

**Tags**: rag-evaluation, reference-free, llm-judge, faithfulness, continuous-metrics, noise-floor
