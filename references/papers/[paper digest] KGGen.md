# KGGen: Extracting Knowledge Graphs from Plain Text with Language Models

**Authors**: Belinda Mo, Kyssen Yu, Joshua Kazdan, Joan Cabezas, Proud Mpala, Lisa Yu, Chris Cundy, Charilaos Kanatsoulis, Sanmi Koyejo (Stanford, Toronto, FAR AI)

**arXiv link (source for re-download)**: https://arxiv.org/abs/2502.09956

**Publication date**: 2025-02-14 (first arXiv version)

## Summary

- Releases **MINE (Measure of Information in Nodes and Edges)** - the first benchmark that scores a text-to-KG extractor on INFORMATION RETENTION: 100 articles (~1,000 words each), 15 gold facts per article; a fact counts as retained if the top-k embedding-similar nodes' local subgraph supports it (LLM-judged)
- Headline retention: **KGGen 66.07% vs GraphRAG 47.80% vs OpenIE 29.84%** - the best published extractor still DROPS ~34% of source facts; GraphRAG drops half
- Mechanism: LLM entity+triple extraction per passage, then an iterative multi-stage clustering pass over the WHOLE graph (LLM-proposed clusters with validation loops) to consolidate synonymous entities and edge labels, attacking sparsity/fragmentation rather than extraction recall
- Frames KG incompleteness as the field's bottleneck: Wikidata/DBpedia/YAGO are "far from complete"; automatic extractors are worse
- Second benchmark (WikiQA-based) measures retrieval accuracy on the generated graphs - KGGen comparable to GraphRAG there, better on retention
- Clustering is global and post-hoc (all nodes at once), contrasting with KGF's incremental Bayesian per-pair resolution

**Relevance to Knowledge Graph Foundry**: The only published quantitative instrument for "does the graph miss information" - and its numbers say ALL current extractors miss 34-70% of facts. Directly grounds KGF's coverage-guarantee ambition: nobody publishes extraction-coverage curves, multi-pass union yields, or per-document retention certificates. MINE's fact-recall protocol is a ready-made template for a KGF self-audit gate (generate fact probes from source, check graph support).
