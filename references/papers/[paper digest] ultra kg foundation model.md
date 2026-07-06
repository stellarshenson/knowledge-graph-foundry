**Towards Foundation Models for Knowledge Graph Reasoning (2023)**

Classical KG embeddings are bound to one fixed entity/relation vocabulary and cannot transfer to a new graph. ULTRA reframes reasoning around relations rather than entities, learning no graph-specific embeddings, so a single pretrained model performs fully-inductive zero-shot link prediction on unseen KGs. Across **57 KGs** zero-shot MRR averages **0.395**, beating supervised-SOTA **0.344**, from a model of only **177k parameters**.

**Key mechanism**
- Build a "graph of relations" - nodes are relation types, edges capture head-to-head and tail-to-tail co-occurrence between relations
- Run a GNN with a labeling trick over that meta-graph to produce relative relation representations
- Run an entity-level NBFNet-style GNN conditioned on those relation representations
- Store no entity or relation embeddings - the same weights transfer to any vocabulary
- Total 177k parameters: 60k relation-GNN + 117k entity-GNN

**Main findings**
- Zero-shot MRR 0.395 across 57 KGs vs supervised-SOTA 0.344; 0.518 Hits@10 zero-shot
- Fine-tuning adds only ~10% relative (MRR 0.422)
- On small inductive graphs (FB-25, FB-50) zero-shot is ~3x baselines

**Key takeaways**
- A relation-relative formulation generalizes across KGs with no per-graph training
- Tiny parameter count makes inference-only deployment cheap
- Pretrained ultra_50g checkpoint available on HuggingFace

**Relevance**
- Most directly deployable mechanism - run the pretrained checkpoint inference-only to score all ~3,900 edges, ranking implausible ones as defect candidates and feeding structural plausibility into cross-type resolution
- Chief risk at our scale: the thin ~12-relation relation-graph may degrade scoring toward chance

**Tags**
- #KnowledgeGraph #FoundationModel #LinkPrediction #ZeroShot

**Source**
- Download: https://arxiv.org/pdf/2310.04562
- Local: [paper] ultra kg foundation model, 2023.pdf
