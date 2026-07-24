# BLINK - Scalable Zero-shot Entity Linking with Dense Entity Retrieval

**arXiv 1911.03814 (EMNLP 2020), Wu, Petroni, Josifoski, Riedel, Zettlemoyer (Facebook AI / UCL / EPFL)**. A two-stage BERT linker where each entity is defined only by a short description: a bi-encoder retrieves candidates in dense space, then a cross-encoder re-ranks. New SOTA on zero-shot EL (**+6 points**) and TACKBP-2010 (**+3**). The canonical statement of the candidate-generation vs disambiguation split with concrete recall targets.

**Key mechanism**
- Stage 1 (candidate generation): bi-encoder independently embeds mention-context and each entity description; exhaustive/FAISS nearest-neighbour retrieves the top-K entities - tuned for RECALL, not final accuracy
- Stage 2 (disambiguation): cross-encoder concatenates mention and entity text for full cross-attention, re-ranking the retrieved candidates for PRECISION
- Zero-shot by design: an entity is only ever a short description, so entities absent from training are still retrievable and rankable
- FAISS exact/approximate NN gives the accuracy-speed knob at scale

**Main findings**
- Stage-1 Recall@64 on the Zero-shot EL dataset: 82.06 (test) / 93.12 (train) for the dense bi-encoder vs 69.13 for BM25 - dense candidate generation beats sparse by ~13 recall points
- The pool is deliberately large: cross-encoder trained on the top-100 bi-encoder candidates; recall@K measured over K up to 64-100
- Overall accuracy is optimized at re-rank depth k=10 even though the retrieval pool is far larger - i.e. retrieve wide (64-100), re-rank a smaller precise window
- Knowledge distillation from the cross-encoder teacher into the bi-encoder student narrows the gap without the re-rank cost

**Key takeaways**
- Two clean, separately-tuned stages: generation maximizes recall@K over a large pool; disambiguation maximizes precision on a small re-rank window - the two objectives are explicitly NOT the same and are NOT tuned together
- Recall@64 ~82-93% is a concrete production-scale candidate-generation target
- Entities-as-descriptions is the zero-shot lever; a graph without descriptions must supply candidate text from node context/aliases

**Relevance to KGF**
- The load-bearing evidence for the H626 anti-alignment FENCE: BLINK proves the field keeps the candidate pool GENEROUS (top-64/100) and pushes precision entirely into a downstream cross-encoder - it never tries to make the candidate CUT precise, exactly matching our finding that candidate precision and walk reachability are anti-aligned at the margin. Max-gap's surplus low-precision anchors are the analogue of BLINK's wide retrieval pool
- Motivates a two-stage KGF hypothesis: keep the generous max-gap anchor set as stage-1 recall mass; add a stage-2 cross-encoder re-rank (question x candidate-node-context) to reorder the off-gold exact-match hubs the H621 finding exposed - re-ranking, not cutting
- Descriptions gap: BLINK's entity tower needs descriptions KGF nodes lack - the re-rank text would have to be assembled from incident-edge context, a real cost to flag

**Tags**
- #EntityLinking #CandidateGeneration #TwoStage #ZeroShot #Reranking #DenseRetrieval

**Source**
- Download: https://arxiv.org/abs/1911.03814
- Local: [paper] BLINK zero-shot entity linking, 2019.pdf
