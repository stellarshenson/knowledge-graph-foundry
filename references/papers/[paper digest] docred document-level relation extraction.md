# DocRED - document-level relation extraction benchmark

**Yao et al., ACL 2019** - arXiv 1906.06127. The task-defining benchmark for relations whose endpoints do not co-occur in one sentence: **5,053 human-annotated Wikipedia documents, 132,375 entities, 56,354 relational facts over 96 relation types**, plus a 101k-document distantly-supervised split.

**Key mechanism**: annotates relations at the document level with supporting-evidence sentences, forcing models to aggregate mentions across sentences via coreference and multi-step reasoning rather than classify single-sentence patterns.

**Main findings**: **40.7% of relational facts can only be extracted from multiple sentences**, and a majority of instances require aggregating information beyond a single mention pair - sentence-level RE systems structurally cannot recover this mass. Follow-up graph-reasoning models improve cross-sentence F1 by building document graphs over mentions, coreference links and sentences.

**Key takeaways for KGF**: formal characterization of failure class (a) - relation endpoint pairs that never share an extraction window. No chunking policy creates co-occurrence that does not exist in a window; the DocRED-lineage design principle is to decouple mention detection (local, per-chunk) from relation inference (global, over the pooled mention set). This is the architectural basis for a document-level relation pass rather than a smarter splitter.

**Tags**: relation-extraction, document-level, cross-sentence, benchmark
**Source**: https://arxiv.org/abs/1906.06127 (PDF: `[paper] docred document-level relation extraction, 2019.pdf`)
