# REXEL: An End-to-end Model for Document-Level Relation Extraction and Entity Linking

**arXiv 2404.12788 (2024), Bouziani et al. (Amazon Science).** REXEL performs mention detection, entity typing, entity disambiguation, coreference resolution, and document-level relation classification in a **single forward pass**, running **11x faster** than competitive pipeline approaches while surpassing baselines by **more than 6 F1 points on average** across individual and combined subtasks.

**Key mechanism**: replaces the traditional closed-information-extraction (cIE) pipeline - separate mention detection, entity linking, coreference, and relation extraction stages prone to cascading error propagation - with one joint model operating at document level (not sentence level), so long-range dependencies across a document are captured natively and facts emerge already linked to a reference KG.

**Main findings**: joint document-level modeling beats both sentence-level cIE and multi-stage pipelines on speed and accuracy simultaneously; the joint model is competitive even when evaluated on any single subtask in isolation, indicating no significant accuracy trade-off for the efficiency gain. Releases a DocRED extension for DocIE benchmarking.

**Key takeaways for KGF**: direct evidence for whether carrier-entity selection (coreference resolution) should fold into the extraction pass rather than sit as a separate downstream stage - REXEL's single-forward-pass design argues for coupling mention resolution and relation extraction, relevant to any KGF redesign considering merging census/extraction stages versus keeping them decoupled. The 11x speed gain from joint modeling is a concrete efficiency argument for pipeline consolidation.

**Tags**: joint-extraction, document-level-ie, entity-linking, coreference, relation-extraction
**Source**: https://arxiv.org/abs/2404.12788 (PDF: `[paper] rexel joint relation extraction entity linking, 2024.pdf`)
