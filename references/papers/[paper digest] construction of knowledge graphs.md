**Construction of Knowledge Graphs: Current State and Challenges**

Hofer, Obraczka, Saeedi, Kopcke and Rahm survey knowledge graph construction across **62 pages**, comparatively evaluating current KG-specific pipelines and toolsets against a set of derived requirements spanning data acquisition (unstructured, semi-structured, structured), metadata management, ontology development, knowledge extraction/completion, entity resolution/fusion, and **quality assurance (QA)** - and find that open-source KG-specific pipelines remain limited on scalability, incremental-update support, and QA/ontology-management maturity, while closed-source toolsets are functionally stronger but unusable for new research.

**Key mechanism**: the paper frames KG construction as a generic incremental pipeline (Figure 2) rather than a one-shot build - knowledge extraction, entity resolution, knowledge completion, and quality assurance are tasks that can each run asynchronously against a live KG, with metadata management as the cross-cutting task threading through the whole pipeline. Quality assurance is explicitly scoped as three sub-problems: identifying quality aspects, detecting violations, and applying repair strategies - continuous operations against an already-built graph, not a one-time validation gate.

**Main findings**: no surveyed pipeline or toolset satisfies all derived requirements simultaneously; incremental/continuous update support, provenance tracking, and integrated ontology management are the weakest points across the field. LLMs are flagged as promising but immature for KG construction tasks (extraction, entity resolution, data integration) as of the survey date (2024).

**Key takeaways for KGF**: this survey grounds the framing of KG quality assurance as a **continuous, ingest-time discipline** rather than a post-hoc audit - directly supporting KGF's panel-as-ingest-instrument design (assortativity/Frechet/certificate-coverage channels computed as the graph grows, not batch-checked afterward). It also confirms that incremental KG construction with integrated QA is an open research gap in the field generally, positioning KGF's self-auditing-foundry approach (audit identity/fidelity/completeness continuously, repair from source, use the gap ledger as an abstention signal) against a genuine SOTA gap rather than a solved problem.

Tags: knowledge-graph-construction, survey, quality-assurance, incremental-construction, ontology-management, entity-resolution

Source: https://doi.org/10.3390/info15080509 (Information 15(8):509, 2024, MDPI open access)
