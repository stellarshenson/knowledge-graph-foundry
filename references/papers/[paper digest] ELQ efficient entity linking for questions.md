# ELQ - Efficient One-Pass End-to-End Entity Linking for Questions

**arXiv 2010.02413 (EMNLP 2020), Li, Min, Iyer, Mehdad, Yih (MIT CSAIL / UW / Facebook AI)**. A bi-encoder that jointly does mention detection and linking over a QUESTION in one BERT pass, beating prior SOTA by **+12.7 F1** (WebQSP) and **+19.6 F1** (GraphQuestions) at **1.57 examples/s on a single CPU** (~2x faster than any neural baseline). The single most relevant paper to KGF's query->graph linking layer: it links questions, not documents, and treats questions as short, noisy, casing-free text.

**Key mechanism**
- Two separately-encoded towers: an entity encoder embeds every Wikipedia entity once from its short description (`x_e = BERT_CLS([CLS] title [ENT] desc [SEP])`); a question encoder produces token-level embeddings for the query
- Mention detection scores EVERY span `[i,j]` up to length L=10 as a candidate mention; kept if `p([i,j]) > gamma` (a single threshold hyperparameter)
- Disambiguation is inner product between the averaged mention-token embedding and entity embeddings; the joint score `p(e,[i,j]) = p(e|[i,j]) * p([i,j])` is thresholded by the SAME gamma
- All inputs lowercased (case-insensitive by construction) to survive question noise; FAISS used only for hard-negative mining during training, exhaustive inner product at inference

**Main findings**
- WebQSP-EL: Precision 90.0 / Recall 85.0 / F1 87.4, versus VCG 82.4 / 68.3 / 74.7 - the recall gain is the headline (+16.7 recall points over VCG)
- Zero-shot transfer to GraphQuestions (trained only on WebQSP): 60.1 / 57.2 / 58.6 F1, still beating a supervised VCG
- NIL / unlinkable handling is entirely a threshold decision: a span whose best entity score never clears gamma is simply not emitted - there is no score-curve-shape analysis, no per-candidate conformal step
- Plugging ELQ into GraphRetriever lifts downstream open-domain QA by up to 6%

**Key takeaways**
- The keep/drop decision is one tuned scalar on the joint mention x entity score - a learned threshold on a MEANINGFUL score (context-entity compatibility), not on the geometry of a candidate ranking curve
- Generous span enumeration (all spans up to L=10) with a downstream compatibility threshold is the candidate-generation-then-filter split in its purest form
- Case-folding at both index and query time is a design choice, not an afterthought, precisely because questions lack the casing cues documents provide

**Relevance to KGF**
- Directly against the H623/H624/H626 score-shape FENCE: ELQ's NIL cut is a threshold on an absolute context-entity compatibility score, NOT on the shape of a same-mention candidate curve. Our closed axis tried to read the curve's geometry; ELQ never does - it reads one calibrated inner-product magnitude. A candidate hypothesis is a context-entity compatibility scorer (question-embedding vs candidate-node-embedding) as the keep/drop signal, sidestepping the closed shape axis
- Confirms the H626 anti-alignment finding's remedy direction: ELQ optimizes recall at the candidate stage (85 recall) and lets the joint score carry precision - it does not try to make the candidate CUT itself precise
- The case-fold-both-sides design corroborates the H632/DEF-19 variant ladder's fold rung as standard practice, not a hack
- ELQ has a Wikipedia entity index with descriptions; KGF's self-extracted graph has no descriptions - the entity-embedding tower would have to be built from node context/aliases, a real gap to flag

**Tags**
- #EntityLinking #QuestionLinking #Biencoder #NILThreshold #CandidateGeneration

**Source**
- Download: https://arxiv.org/abs/2010.02413
- Local: [paper] ELQ efficient entity linking for questions, 2020.pdf
