**KGValidator: A Framework for Automatic Validation of Knowledge Graph Construction**

Boylan et al. (Quantexa) introduce an LLM-backed triple-classification validator that reaches up to **95% accuracy on WN18RR-150** (GPT-4, world-knowledge-only context) and **89% on Wiki27K-150** (GPT-4 with combined Wikidata+web retrieval context), evaluated across five benchmark KG-completion datasets - UMLS, WN18RR, FB15K-237N, Wiki27K, CoDeX-S - with GPT-3.5 and GPT-4, using a single fixed prompt across all datasets to avoid prompt-as-overfitting.

**Key mechanism**: the framework treats each candidate (head, relation, tail) triple as a claim to validate, giving the LLM a combination of model-intrinsic world knowledge and externally retrieved context (Wikidata lookups, Wikipedia+Wikidata, live web search) before it renders a correct/incorrect judgment - functioning as a competency-question-style satisfaction check rather than a closed-world lookup. Structural and semantic output validation (via Instructor) constrains the LLM's response to a parseable schema, and the architecture is explicitly designed to plug in arbitrary external knowledge sources or agents.

**Main findings**: added external context (Wikidata, web) generally lifts accuracy over world-knowledge-only prompting, especially for GPT-3.5 (e.g., FB15K-237N accuracy rises from 0.63 with world knowledge alone to 0.82 with Wikidata+web); GPT-4 is more consistently accurate but the context-retrieval gain is smaller and dataset-dependent (UMLS in particular stays weak, ~0.57-0.64 accuracy across all context conditions), showing that context helps most where model-intrinsic knowledge is thin.

**Key takeaways for KGF**: this is the closest published SOTA analogue to KGF's certificate-coverage discipline - LLM-mediated, context-grounded, per-triple validation standing in for the human-annotation bottleneck that made KG QA prohibitively expensive at scale. The dataset-dependent gain from external context (strong on Freebase/Wikidata-derived data, weak on UMLS's closed medical ontology) is a caution for KGF's own certificate design: retrieval-augmented validation is not uniformly reliable and should be weighted by how well the target domain is covered by the retrieval source, not assumed as a universal accuracy lift.

Tags: knowledge-graph-validation, llm-as-judge, triple-classification, competency-questions, retrieval-augmented-validation, quality-assurance

Source: https://arxiv.org/abs/2404.15923 (Boylan, Mangla, Thorn, Ghalandari, Ghaffari, Hokamp - Quantexa, TEXT2KG Workshop 2024)
