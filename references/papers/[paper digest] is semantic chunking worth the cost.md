# Is Semantic Chunking Worth the Computational Cost?

**Qu et al., 2024** - arXiv 2410.13070. Systematic evaluation of fixed-size vs embedding-similarity chunking (breakpoint and clustering variants) across **10 document-retrieval, 5 evidence-retrieval and 5 generation datasets** at three embedding-model tiers. Headline: the computational cost of semantic chunking **is not justified by consistent gains**.

**Key mechanism**: breakpoint chunking cuts where adjacent-sentence embedding cosine distance spikes past a percentile threshold; clustering chunking groups semantically similar sentences. Both require a full sentence-embedding pass at ingest.

**Main findings**: fixed-size chunking matched or beat semantic variants on real documents - HotpotQA document-retrieval **F1@5: fixed 90.59 vs breakpoint 87.37 vs clustering 84.79**; ExpertQA evidence retrieval F1@5 statistically tied (47.11 / 47.08 / 46.87); answer-generation BERTScore identical at 0.65. Semantic chunking won only on artificially stitched high-topic-diversity corpora that do not resemble natural documents.

**Key takeaways for KGF**: all evidence is retrieval-side, none extraction-side, and it is negative even there - embedding-drift chunking is excluded from the R32 fanout as a pre-registered dead end. The sentence-embedding drift signal is additionally noisy around tables/spec regions, the dominant content class in the benchmark corpus.

**Tags**: chunking, semantic-chunking, negative-result, retrieval
**Source**: https://arxiv.org/abs/2410.13070 (PDF: `[paper] is semantic chunking worth the cost, 2024.pdf`)
