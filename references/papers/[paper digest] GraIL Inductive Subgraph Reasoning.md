**Inductive Relation Prediction by Subgraph Reasoning (GraIL, 2020, ICML)**

GraIL scores a candidate triple (h, r, t) from the STRUCTURE of the subgraph enclosing h and t, using no entity embeddings - so it generalizes inductively to unseen entities and even unseen graphs. It reasons over local subgraph topology with a relational GNN and is proven to represent a useful subset of first-order logic (path rules). Ensembling GraIL with KG-embedding methods yields significant gains, showing structure and embedding are complementary.

**Key mechanism**
- Extract the enclosing subgraph around the (h, t) pair
- Label each node by its double-radius distance to h and to t (structural role, not identity)
- Relational GNN scores whether target relation r holds - conditioned on r's type, independent of specific entities

**Main findings**
- Fully inductive: transfers to unseen entities/graphs after training (embedding methods cannot)
- Represents a useful subset of first-order logic - captures compositional path rules
- GraIL + KGE ensemble beats either alone (structure complements embedding on clean KGs)

**Key takeaways**
- The enclosing-subgraph-around-a-pair is exactly the "speculative topology region" primitive R50 describes
- Entity-independent structural reasoning is the learned analogue of a typed-path walk (H592)
- Conditions explicitly on a clean relation type r - its whole inductive bias assumes a curated relation vocabulary

**Relevance**
- GraIL is the learned form of H583's topology oracle / H592's typed walk: "could relation r connect h and t via a typed path?"
- Its dependency on clean relation types collides head-on with the H585 risk - KGF's 334 self-extracted relations (entropy 6.22) would fragment GraIL's relation conditioning; this is the single sharpest kill for a GraIL-class KGF matcher
- The GraIL+KGE-complementary result is the clean-KG counterpart to KGF's H95, where structure HURT identity on the noisy self-extracted graph - the same mechanism, opposite sign, because vocabulary cleanliness flips it

**Tags**
- #InductiveReasoning #SubgraphReasoning #RelationPrediction #FirstOrderLogic

**Source**
- Download: https://arxiv.org/pdf/1911.06962
- Local: [paper] GraIL Inductive Subgraph Reasoning, 2020.pdf
