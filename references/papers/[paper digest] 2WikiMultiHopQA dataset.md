**Constructing A Multi-hop QA Dataset for Comprehensive Evaluation of Reasoning Steps (2020)**

Prior multi-hop reading-comprehension datasets (HotpotQA in particular) suffered two flaws: many "multi-hop" questions were solvable single-hop, and none supplied a structured explanation of the reasoning chain from question to answer. 2WikiMultiHopQA's shift is to generate questions from Wikidata triples under hand-verified templates and logical rules, so every question carries a machine-checkable **evidence** field - a set of KG triples forming the exact reasoning path - alongside the usual answer and supporting-sentence labels. The result is a **192,606-question** dataset spanning four reasoning types, harder than HotpotQA by every quality metric the authors test (single-hop BERT F1 drops **8.7 points** relative to HotpotQA on the same architecture).

**Key mechanism**
- Built from the intersection of Wikipedia summaries (unstructured) and Wikidata triples (structured) - a question is only generated if the KG-derived answer text is verifiably present in the entity's Wikipedia paragraph
- Four question types from distinct templates: comparison (two same-group entities compared on an attribute), inference (two chained triples collapsed via a verified logical rule into a new relation, e.g. spouse+mother -> mother-in-law), compositional (same two-triple chain but no valid inference relation exists, so the question nests sub-questions), and bridge-comparison (bridge-entity lookup plus comparison)
- 28 logical rules manually verified against Wikidata (from 50 AMIE-mined candidates) drive inference-question generation
- Evidence field = the 1-2 KG triples used to derive the answer, enabling a "joint" metric (Joint F1/EM) multiplying precision/recall across answer span, supporting sentences, and evidence triples together
- Distractor paragraphs (8-10 per example) via bigram TF-IDF + entity-type matching, mirroring HotpotQA's distractor setting
- Post-generation filtering discards ambiguous cases (e.g. multiple qualifying children under a grandchild rule) via Wikidata

**Main findings**
- Dataset scale: **192,606 total examples** (154,878 train-medium, 12,576 each of train-hard/dev/test); compositional questions dominate (86,979), inference smallest (7,478, constrained by a unique-answer requirement)
- Difficulty check: the same baseline architecture scores answer EM/F1 of **34.14/40.95** here vs **44.48/58.54** on HotpotQA, despite comparable human upper bounds (91.8 vs 98.8 F1) - the questions are objectively harder, not noisier
- Multi-hop necessity check (single-hop BERT probe): F1 of **55.9** here vs **64.6** on HotpotQA - an **8.7-point drop**, evidence single-hop shortcuts are less available
- Baseline joint task (answer + supporting-facts + evidence): test EM of **36.53 answer / 24.99 supporting-facts / 1.07 evidence / 0.35 joint** - evidence generation is far from saturated (human upper bound 64.00 EM / 78.81 F1 vs model's ~1/17)
- Answer-type distribution: yes/no (31.2%), date (16.9%), film (13.5%), human (11.7%), remaining spread across 708 distinct Wikidata types

**Key takeaways**
- A dataset can enforce genuine multi-hop necessity at construction time (logical-rule verification, paragraph-presence checks) rather than relying on post-hoc model-based difficulty probes
- Structured evidence (explicit KG triples) as a first-class label lets a system's reasoning path be scored independently of whether the final answer span matches
- The four-type taxonomy (comparison/inference/compositional/bridge-comparison) is a reusable typology for what "multi-hop" structurally means, distinct from raw hop count

**Relevance**
- 2WikiMultiHopQA is KGF's primary bench-only ladder corpus; this paper is the ground-truth schema for what "gold reasoning path" and "question type" mean in every R50 hypothesis consuming the corpus's evidence triples or the structural 4-class question-TYPE label
- The four-way typology maps directly onto R50-H593's shape-driven two-slot seeding for the comparison class and the bridge/inference distinction behind several R50 topology hypotheses

**Tags**
- #Benchmark
- #MultiHopQA
- #DatasetConstruction
- #EvidencePath
- #Wikidata

**Source**
- Download: https://arxiv.org/abs/2011.01060
- Local: [paper] 2WikiMultiHopQA dataset, 2020.pdf
