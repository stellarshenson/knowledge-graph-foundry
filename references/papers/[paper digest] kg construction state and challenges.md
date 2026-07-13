**Construction of Knowledge Graphs: State and Challenges (Hofer et al., 2023)**

Survey of **51 pages, 328 references** covering the full KG construction pipeline from unstructured (text) and structured (database) sources, concluding that individual construction steps are well-studied in isolation but their integration for **ongoing incremental updates and collaborative maintenance remains understudied**.

Key mechanism:
- Surveys principal graph models used for KGs (property graph, RDF, hypergraph) and the phases a construction framework must cover: metadata handling, schema design, entity/relation extraction, and validation
- Distinguishes **batch (full rebuild) construction** from **incremental (delta) construction** as separate architectural concerns, each with distinct cost, consistency, and staleness tradeoffs
- Assesses current implementations across notable production KGs and emerging construction tools against these requirement phases

Main findings:
- No surveyed framework fully solves incremental construction with the same rigor applied to one-shot batch construction; incremental pipelines tend to bolt updates onto batch-oriented designs rather than treat delta-processing as first-class
- Validation and schema management are typically treated as post-hoc rather than integrated into the construction loop
- Collaborative/multi-source construction (merging KG contributions from independent pipelines) is identified as the least mature area

Key takeaways (relevance to KGF): the paper's incremental-vs-batch framing is a distinct cost axis from per-document instrumentation overhead - a pipeline can be cheap to instrument per-document while still being expensive to update incrementally, or vice versa. This separation keeps KGF's per-doc telemetry claims from being conflated with claims about incremental-update savings, and supports treating "cost of watching a document" and "cost of updating the graph after a document changes" as independently measurable.

Tags: kg-construction, survey, incremental-update, batch-construction, schema-validation

Source: https://arxiv.org/abs/2302.11509
