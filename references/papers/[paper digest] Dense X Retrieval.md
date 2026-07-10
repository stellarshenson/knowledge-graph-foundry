**Dense X Retrieval: What Retrieval Granularity Should We Use?, Chen et al. (Tencent AI Lab / CMU), 2023-12**

Propositions - atomic, self-contained factoid sentences generated at ingest - as the retrieval unit instead of passages or sentences. Indexing Wikipedia as **257M propositions** (FactoidWiki, from 41M passages, avg **11.2 words**, 6.3 propositions/passage) lifts unsupervised dense retrievers by **+12.0 (SimCSE) and +9.3 (Contriever) Recall@5** on average across five open-domain QA datasets (**+35.0% / +22.5% relative**), and supervised retrievers by +2.7 Recall@20 in-domain with much larger gains out-of-domain (GTR **+16% relative Recall@5 on SQuAD**). Proposition-level indexing gives the highest downstream QA exact match for all four retrievers under a fixed token budget.

**Key mechanism**
- "Propositionizer" = Flan-T5-large finetuned by two-step distillation from GPT-4 (42k labeled passages, F1 0.822) decomposes each passage into minimal, self-contained propositions with pronouns resolved and context inlined
- Each proposition is embedded and indexed as its own retrieval unit, pointing back to its source passage
- Query-time is unchanged dense retrieval; the granularity shift means the query embedding meets small single-fact units, not multi-topic passages
- Retrieved propositions are mapped back to passages or used directly as reader context

**Main findings**
- Recall@5 +12.0/+9.3 unsupervised; Recall@20 +10.1 average; supervised retrievers gain mostly out-of-domain (generalization)
- Higher density of question-relevant information per retrieved token - best QA EM at fixed context budget
- Index growth is the cost: 6.3x more units, ~768GB index; propositionizer inference over the whole corpus at ingest
- Weakness: multi-hop questions needing combination of facts across long ranges - atomic units fragment the evidence

**Key takeaways**
- Decontextualized, atomic generated objects are better embedding targets than raw chunks - the semantic-match problem shrinks when the unit carries exactly one fact
- The gains concentrate where the retriever is weakest (unsupervised, out-of-domain) - generated units compensate for encoder limitations
- Unit granularity trades single-fact precision against multi-fact recall; a system serving both needs multiple coexisting granularities

**Tags**: #Propositions #RetrievalGranularity #DenseRetrieval #IndexTimeGeneration #FactoidWiki

**Source**: https://arxiv.org/abs/2312.06648. Local: [paper] Dense X Retrieval, 2023-12.pdf
