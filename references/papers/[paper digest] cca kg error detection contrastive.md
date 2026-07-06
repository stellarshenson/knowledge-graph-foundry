**Knowledge Graph Error Detection with Contrastive Confidence Adaption (2023)**

CCA addresses error detection in automatically-built KGs, arguing that prior structure-only detectors fail on "semantically-similar noise" - wrong triples whose entities are still topically related, precisely how LLM extraction errors look. It fuses textual and structural signal to score triple confidence. On FB15K-237 with 5% mixed noise it reaches precision@top-5% **0.534** vs CAGED **0.467** and CSProm-KG **0.509**, but the diagnostic finding is that realistic noise is genuinely hard for every detector.

**Key mechanism**
- Reconstruction classifier: BERT encodes textual descriptions, a Transformer encodes graph structure, both reconstructing masked head/tail entities to yield confidence scores
- Interactive contrastive learning aligns textual and structural embeddings against entity-replacement negatives
- Knowledge fusion combines the two views into pseudo-labels

**Main findings**
- FB15K-237 (5% mixed noise): precision@top-5% 0.534 vs CAGED 0.467, CSProm-KG 0.509
- WN18RR: 0.733 vs KG-BERT 0.710, CAGED 0.421
- CAGED precision collapses 0.945 → 0.633 from random to similar noise
- Even CCA reaches only 0.453 (similar) and 0.240 (adversarial) on FB15K-237

**Key takeaways**
- Structure-only detectors break exactly on semantically-similar noise
- Text+structure fusion is required, yet error detection stays hard on realistic noise
- Absolute precision on adversarial noise is low - a sober ceiling

**Relevance**
- Confirms our failure mode is the hardest case for structural detectors
- Text+structure fusion is required, not optional
- At 2,800 entities, adapt the contrastive setup with synthesized errors rather than adopt it wholesale

**Tags**
- #KnowledgeGraph #ErrorDetection #ContrastiveLearning

**Source**
- Download: https://arxiv.org/pdf/2312.12108
- Local: [paper] cca kg error detection contrastive, 2023.pdf
