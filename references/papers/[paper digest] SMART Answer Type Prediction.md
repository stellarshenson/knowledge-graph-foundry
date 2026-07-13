**SeMantic AnsweR Type Prediction Task (SMART) at ISWC 2020 Semantic Web Challenge (2020)**

A short task-description paper (no participant results reported) introducing SMART, a shared task that reframes answer-type prediction from coarse TREC-style categories (6-50 classes) to fine-grained ontology classes: given a natural language question, predict a ranked list of answer types from a target knowledge-base ontology (DBpedia or Wikidata). The benchmark is assembled from **44,762 total questions** (21,940 DBpedia-typed, 22,822 Wikidata-typed) mined out of three existing KBQA datasets - QALD-9, LC-QuAD v1.0, and LC-QuAD v2.0 - by executing each dataset's gold SPARQL query and manually validating the resulting answer type, rather than annotating from scratch.

**Key mechanism**
- Each question is labeled with an answer category (resource / literal / boolean) and, conditional on category, an answer type: an ontology class for "resource" (e.g. dbo:Actor, wd:Q33999), one of number/date/string for "literal", or "boolean" itself
- Systems must predict both fields per question: category prediction is scored by plain classification accuracy; type prediction uses NDCG@k with linear decay (Balog and Neumayer's hierarchical target-type identification metric), which gives partial credit for predicting a type that sits near the true type in the ontology's class hierarchy rather than requiring an exact match
- Gold labels are derived, not hand-written: the organizers ran each question's existing gold SPARQL query against the KB, inferred the answer type(s) from the returned entities' classes, and manually validated the result - reusing three established KBQA benchmarks rather than authoring type labels from scratch

**Main findings**
- No participant system results appear in this paper - it is purely the task, dataset, and metric definition released ahead of the ISWC 2020 challenge (leaderboard and code hosted separately at smart-task.github.io)
- Dataset composition: DBpedia set is 17,571 train / 4,369 test (9,584 resource, 2,799 boolean, 5,188 literal - split 1,634 number / 1,486 date / 2,068 string in train); Wikidata set is 18,251 train / 4,571 test (11,683 resource, 2,139 boolean, 4,429 literal)

**Key takeaways**
- Fine-grained, ontology-class-level answer typing is achievable at scale by mining gold SPARQL execution results from existing KBQA benchmarks rather than hand-annotating a new corpus from scratch
- The hierarchical/lenient NDCG@k metric rewards a predicted type that is an ancestor or descendant of the true type in the class hierarchy over a flat, unrelated wrong guess - graded credit rather than binary exact-match

**Relevance**
- This is the canonical formalization of "typed retrieval" as a distinct pre-retrieval step: answer-type prediction narrows the candidate entity type before any path or topology traversal begins, which is exactly the "typed" half of R50's typed/topology retrieval axis
- The graded, hierarchy-aware type-match metric is directly reusable for KGF's own type-prediction or type-conformance scoring - a near-miss on the type hierarchy (predicting a supertype or sibling type) should score better than a random wrong type, the same way it does here

**Tags**
- #AnswerTypePrediction
- #TypedRetrieval
- #KBQA
- #OntologyClassification

**Source**
- Download: https://arxiv.org/pdf/2012.00555
- Local: [paper] SMART Answer Type Prediction, 2020.pdf
