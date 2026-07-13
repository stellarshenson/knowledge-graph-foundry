# Precise Zero-Shot Dense Retrieval without Relevance Labels (HyDE)

**Authors**: Luyu Gao, Xueguang Ma, Jimmy Lin, Jamie Callan

**arXiv link (source for re-download)**: https://arxiv.org/abs/2212.10496

**Publication date**: 2022-12-20 (first arXiv version)

## Summary

- On TREC DL19, HyDE reaches **41.8 MAP / 61.3 nDCG@10 / 88.0 Recall@1k**, versus zero-shot Contriever's 24.0 / 44.5 / 74.6 and BM25's 30.1 / 50.6 / 75.0 - comparable to the fine-tuned ContrieverFT (41.7 / 62.1 / 83.6)
- On DL20, HyDE scores **38.2 MAP / 57.9 nDCG@10 / 84.4 Recall@1k**, again far above Contriever (24.0 / 42.1 / 75.4) and close to ContrieverFT
- On six low-resource BEIR tasks, HyDE improves nDCG@10 over Contriever on every set (e.g. Scifact 69.1 vs 64.9, Arguana 46.6 vs 37.9, FiQA 27.3 vs 24.5), and beats BM25 on five of six - the exception is TREC-Covid, where HyDE (59.3) trails BM25 (59.5) by a 0.2-point margin while Contriever alone collapses to 27.3
- On Mr.TyDi multilingual retrieval (MRR@100), HyDE lifts mContriever from 38.3/22.3/19.5/35.3 to **41.7/30.6/30.7/41.3** across Swahili/Korean/Japanese/Bengali
- Scaling the instruction-following generator matters more than scaling the encoder: on DL19/20 nDCG@10, HyDE with FLAN-T5-11b reaches 48.9/52.9, Cohere-52b reaches 53.8/53.8, and GPT-175b (InstructGPT) reaches 61.3/57.9 - larger generators give larger gains
- No model is trained or fine-tuned to build HyDE; it composes an off-the-shelf instruction-following LLM (InstructGPT / text-davinci-003) with an off-the-shelf unsupervised contrastive encoder (Contriever)

**Key mechanism**
- Given a query, an instruction-following LLM is prompted zero-shot (e.g. "write a passage to answer the question") to generate a hypothetical document - unreal, possibly factually wrong, but relevance-shaped
- The hypothetical document is encoded by an unsupervised contrastive encoder (Contriever); its dense bottleneck acts as a lossy compressor that filters out the hallucinated specifics while retaining the relevance signal
- The resulting vector is used for ordinary inner-product search against the real corpus embeddings - retrieval never scores query-document similarity directly, it is factored into an NLG task (generation) and an NLU task (document-document similarity)
- Query-document relevance modeling is offloaded entirely to the LLM's generative capability; the encoder never needs to have learned relevance, only document-document similarity, so the whole pipeline needs zero relevance labels and zero task-specific training

**Relevance to Knowledge Graph Foundry**: KGF's dense@16 retrieval channel (0.854) is a candidate application point for HyDE - generating a hypothetical answer passage from the query before embedding could sharpen the vector that seeds PPR, particularly for queries whose phrasing diverges from the corpus's entity/relation vocabulary; worth an isolated hypothesis round rather than a blind swap, since HyDE's own numbers show gains concentrate where the base encoder is weak (Contriever) and shrink as the underlying retriever strengthens (ContrieverFT), which may already describe KGF's calibrated, graph-augmented regime.
