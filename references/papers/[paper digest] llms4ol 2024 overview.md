**LLMs4OL 2024 Overview: The 1st Large Language Models for Ontology Learning Challenge (2024)**

This shared challenge asks whether LLMs can perform ontology learning end to end across three tasks - term typing, taxonomy discovery, and non-taxonomic relation extraction - over 21 subtasks and five knowledge sources, with 14 teams. Term typing is nearly solved (best F1 **0.9938** on WordNet), taxonomy discovery is much harder, and non-taxonomic relation extraction largely fails (best F1 **0.0783** on UMLS).

**Key mechanism**
- Shared challenge: term typing, taxonomy discovery, non-taxonomic relation extraction
- 21 subtasks over WordNet, GeoNames, UMLS, Schema.org, GO
- Zero-shot and few-shot settings, 14 teams

**Main findings**
- Term typing nearly solved: best F1 0.9938 WordNet, 0.9382 UMLS-MEDCIN
- Taxonomy discovery much harder: best F1 0.6557 GeoNames, 0.6157 Schema.org
- Non-taxonomic relation extraction largely fails: best F1 0.0783 UMLS, two teams
- Fine-tuning beat zero-shot/few-shot and RAG; biomedical/GO typing hardest (F1 0.27-0.30)
- "smaller models performed adequately when there are fewer types... as the number of types increases, larger models tend to perform better"

**Key takeaways**
- Multi-label term typing is the reliably solvable ontology-learning task
- Taxonomy and relation elicitation from LLMs are inherently risky
- Fewer types favor smaller models; more types favor larger ones

**Relevance**
- Calibrates expectations - our multi-label typing matches the solved task; the flat-ish ontology and consolidated relations sit exactly where LLMs are weak (may be a correct reflection of what is reliably extractable, not a defect)
- Our 9-12 type regime is where a local 120B suffices
- Flags LLM taxonomy elicitation as inherently risky

**Tags**
- #OntologyLearning #LLM #Benchmark #TermTyping

**Source**
- Download: https://arxiv.org/pdf/2409.10146
- Local: [paper] llms4ol 2024 overview, 2024.pdf
