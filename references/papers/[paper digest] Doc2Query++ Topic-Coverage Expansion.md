**Doc2Query++: Topic-Coverage based Document Expansion and its Application to Dense Retrieval via Dual-Index Fusion, Kuo, Chiu, Ma, Cheng (NTU / Academia Sinica), 2025 (arXiv 2510.09557)**

The interference-curve paper for ingest-time query generation. Document expansion by query generation suffers three named failures: uncontrolled generation producing hallucinated or redundant low-diversity queries, poor generalisation from MS MARCO to BEIR, and **noise from concatenation harming dense retrieval**.

**Key mechanism**
- Infer a document's latent topics with unsupervised topic modelling (domain-independent), then use hybrid keyword selection to build a diverse, relevant keyword set per document
- Prompt the LLM with those keywords so the generated queries cover the topics and avoid redundancy
- **Dual-Index Fusion**: keep text and generated-query signals in separate indices and fuse at retrieval, rather than concatenating queries into the passage text - concatenation is what poisons dense retrieval

**Main findings**
- Scaling generated queries per document from 0 to 600 on FiQA-2018 with sparse retrieval: performance **peaks around 100 queries and degrades afterwards** - an explicit interference curve
- Standard docTTTTTquery configurations use 40-80 queries per passage; the degradation past the peak is attributed to hallucinated queries
- Concatenating generated queries into passages helps sparse retrieval but hurts dense retrieval, which is why isolation of signals is needed

**Key takeaways**
- Generated-question count is a **measured budget with an optimum and a decline**, and the decline is caused by low-quality generations, not by count alone
- For dense retrieval specifically, appending generated questions to the indexed text is a documented regression; separate indices with fusion is the published fix
- Combined with QuOTE's ~10 questions/chunk optimum and Doc2Query--'s +16% from filtering, the literature's consistent message is: filter hard, keep the count modest, isolate the signal

**Tags**: #DocumentExpansion #QueryGeneration #Interference #DualIndex #DenseRetrieval #R59

**Source**: https://arxiv.org/abs/2510.09557. Local: [paper] Doc2Query++ Topic-Coverage Expansion, 2025.pdf
