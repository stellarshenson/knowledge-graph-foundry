**Doc2Query--: When Less is More, Gospodinov, MacAvaney, Macdonald, ECIR 2023**

The budgeting/quality-control paper for index-time query generation. Seq2seq expansion models hallucinate queries not grounded in the source passage; scoring every generated query with a relevance model and dropping the low-scoring ones improves retrieval effectiveness by up to **16%**, cuts mean query execution time by **23%**, and shrinks the index by **33%** versus unfiltered docTTTTTquery on MS MARCO. Filtering is a pure win: fewer generated objects retained, better retrieval.

**Key mechanism**
- Generate queries per passage as in docTTTTTquery
- Score each (generated query, source passage) pair with a neural relevance model (cross-encoder re-ranker used as a filter)
- Keep only queries above a score threshold; append survivors to the passage and index
- The filter removes hallucinated queries - queries the passage cannot actually answer - before they pollute the index

**Main findings**
- Up to +16% retrieval effectiveness over unfiltered Doc2Query on MS MARCO
- Index size -33%, mean query execution time -23%
- Hallucinated generated queries actively harm retrieval, not just bloat the index - unfiltered expansion is below the filtered optimum
- The relevance-filter cost at index time is small relative to generation cost

**Key takeaways**
- Generated retrieval objects need a quality gate: generation quality, not generation volume, drives effectiveness
- A grounded-in-source check (can this passage answer this query?) is the canonical filter - directly analogous to an entailment/groundedness gate at ingest
- Establishes rank-then-keep as the standard budgeting pattern for ingest-generated queries

**Tags**: #Doc2Query #QueryFiltering #Hallucination #IndexBudgeting #ECIR

**Source**: https://arxiv.org/abs/2301.03266. Local: [paper] Doc2Query--, 2023-01.pdf
