**Seven Failure Points When Engineering a Retrieval Augmented Generation System (Barnett et al., 2024)**

An experience report from **three deployed RAG case studies** (research, education, biomedical) that names **seven failure points (FP1-FP7)** spanning the whole pipeline from corpus to rendered answer - the closest thing the applied-RAG literature has to a standard failure taxonomy.

**Key mechanism**
- Ordered pipeline taxonomy: each FP is the stage where the answer-carrying information is lost, from "not in the corpus" through "retrieved but not consolidated" to "in context but mis-rendered"
- FP1 Missing Content - answer is not in any available document (corpus gap)
- FP2 Missed the Top Ranked Documents - answer document exists but ranks below the top-K cutoff returned
- FP3 Not in Context (consolidation-strategy limits) - answer document retrieved but dropped during context consolidation/reranking
- FP4 Not Extracted - answer present in context but the LLM fails to extract it (noise/contradiction)
- FP5 Wrong Format - format instruction (table/list) ignored
- FP6 Incorrect Specificity - answer too general or too specific for the need
- FP7 Incomplete - answer omits information that was present and extractable

**Main findings**
- The taxonomy is a pipeline partition by loss-stage, not an overlapping symptom list - FP1-FP4 are a clean retrieval->consolidation->render cascade
- Two takeaways: RAG validation is only feasible during operation (not designable up front); robustness evolves rather than being engineered in at the start
- No frequency data - it is a qualitative field taxonomy, not a measured failure distribution

**Key takeaways**
- FP2 is exactly a rank-below-cutoff miss; FP3 is a lose-during-consolidation miss; FP4 is a present-but-unread miss - the same three-stage split appears independently in production practice

**Relevance to KGF atlas (R57)**
- Direct external validation of the **H620 decomposition**: FP1 = carrier absent from corpus, FP2 = carrier_not_retrieved (our linker/dense axes - rank below the adaptive/top-16 cutoff), FP3 = retrieved_not_rendered (consolidation drop), FP4 = rendered_answer_absent (reader miss). Our three H620 classes collapse Barnett's FP1-FP4 into the coarser retrieve/render/read cut we already draw
- FP5/FP6/FP7 (format, specificity, completeness) are render/reader classes our atlas currently folds into a single render-status flag - a candidate refinement if render misses need sub-typing
- FP2's "top-K selected for performance" framing is the literature's name for our **near-miss shelf (rank 17-64)**: the answer is ranked, just below the operational cutoff - Barnett treats this as a first-class, expected failure mode, supporting the shelf as a real atlas axis rather than an artifact
- Gap the atlas lacks: an explicit **corpus-gap / FP1 class** (answer-carrier not present at any depth) distinct from carrier_not_retrieved - the atlas assumes a gold entity exists in the graph; FP1 is the "no carrier anywhere" terminal case

**Tags**: rag-failure-taxonomy, failure-points, retrieval-vs-render, consolidation, pipeline-diagnosis

**Source**: https://arxiv.org/abs/2401.05856
