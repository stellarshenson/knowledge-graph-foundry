**OWL2Vec*: Embedding of OWL Ontologies (2020)**

OWL2Vec* embeds OWL ontologies so that graph structure, lexical labels, and logical constructors all survive in vector space. It walks the ontology's graph projection to generate three corpora and trains Word2Vec over them. Its load-bearing ablation shows the lexical and word signal is where the performance lives - word-based embeddings reach FoodOn subsumption MRR **0.213** versus **0.154** for structure-only.

**Key mechanism**
- Walk the ontology's graph projection to generate three corpora: structure+constructors, lexical (names, comments, definitions), combined
- Train Word2Vec over the corpora
- Represent entities by IRI embeddings or by averaged word embeddings of their labels

**Main findings**
- FoodOn subsumption MRR 0.213 / Hits@1 0.143 vs OPA2Vec 0.093/0.058 (+129% MRR)
- GO subsumption 0.170 vs 0.075
- HeLis membership MRR 0.953 / Hits@1 0.932 vs RDF2Vec 0.345/0.219
- Ablation: structure-only MRR 0.154 on FoodOn, +lexical 0.183, word-based 0.213

**Key takeaways**
- Lexical/word signal drives performance, not structure alone
- Embedding geometry works where axioms are scarce but names are rich
- Word2Vec over ontology walks is a cheap, strong baseline

**Relevance**
- Strongest evidence that for an ontology poor in axioms but rich in names/descriptions, embedding geometry over LEXICAL content is the productive lever - precisely our situation
- Justifies embedding-first approaches over axiom-based methods we cannot feed

**Tags**
- #OntologyEmbedding #Word2Vec #LexicalSignal #Subsumption

**Source**
- Download: https://arxiv.org/pdf/2009.14654
- Local: [paper] owl2vec ontology embedding, 2020.pdf
