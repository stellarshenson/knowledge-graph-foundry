**Task-based Ontology Evaluation for Question Generation (2025)**

There has been no principled way to say one ontology is better than another for a downstream task. This paper proposes ROMEO, a Goal-Question-Metric adaptation that generates questions from RDF patterns, has experts judge the output, and derives task-specific ontology metrics. Ontologies poor in class richness and population generate few and shallow questions, matching their measured deficits.

**Key mechanism**
- ROMEO (Requirements-Oriented Methodology for Evaluating Ontologies), a Goal-Question-Metric adaptation
- Generate questions from RDF patterns, expert-judge the output
- Derive task-specific ontology metrics: pattern coverage, class richness, average population, inheritance richness, relationship diversity, average connectivity, sibling fan-outness, average depth

**Main findings**
- African Wildlife scored class-richness 0 and average-population 0, producing only 25 terminology questions
- Solar System with pattern coverage 1.0 generated all question types
- A Music validation ontology (CR 0.03, population 0.2) correctly predicted poor class/property-question performance

**Key takeaways**
- Ontology fitness is measured against a concrete downstream task, not in the abstract
- The derived metrics are computable directly on the graph
- Metrics assume instance-populated, authored ontologies

**Relevance**
- The template for measuring whether our cured ontology fits the probe/retrieval task - rerun the requirement-to-metric derivation against probe-answering; every metric is computable on the Neo4j graph
- Caveat: metrics assume instance-populated authored ontologies; re-derive, do not copy

**Tags**
- #OntologyEvaluation #QuestionGeneration #GoalQuestionMetric

**Source**
- Download: https://arxiv.org/pdf/2504.07994
- Local: [paper] task-based ontology evaluation, 2025.pdf
