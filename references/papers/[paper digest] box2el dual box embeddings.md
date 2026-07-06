**Dual Box Embeddings for the Description Logic EL++ (2023)**

Prior EL ontology embeddings fail on one-to-many relations and role inclusions. Box2EL represents both concepts and roles as axis-aligned boxes, giving each role separate head and tail boxes so those constraints become box-inclusion relations, and is proven sound with respect to EL++ semantics. It sets SOTA on subsumption prediction and role assertion, with median rank **~60% lower** than the second-best on GALEN.

**Key mechanism**
- Represent concepts AND roles as axis-aligned boxes
- Give each role separate head and tail boxes so one-to-many relations and role inclusions become box-inclusion constraints
- A bumping mechanism translates entities
- Proven sound with respect to EL++ semantics

**Main findings**
- SOTA on subsumption prediction, role assertion, approximating deductive reasoning
- Median rank ~60% lower than second-best on GALEN, >80% lower on GO, >40% lower on Anatomy

**Key takeaways**
- Box containment carries subsumption faithfully
- The method consumes an existing axiomatized EL++ TBox over tens of thousands of classes
- The geometric idea transfers even where the axioms do not

**Relevance**
- Strongest current argument that geometry (box containment) carries subsumption faithfully - BUT it consumes an existing axiomatized EL++ TBox over tens of thousands of classes; our flat discovered 12-type ontology supplies almost no axioms, so it does not apply off the shelf
- Value: the transferable geometric idea - fit boxes over entity embeddings per type, test containment to find latent hierarchy or type-assignment errors - a repurposing the paper neither does nor validates

**Tags**
- #OntologyEmbedding #DescriptionLogic #BoxEmbeddings #Subsumption

**Source**
- Download: https://arxiv.org/pdf/2301.11118
- Local: [paper] box2el dual box embeddings, 2023.pdf
