**Document Expansion by Query Prediction (doc2query), Nogueira, Yang, Lin, Cho, 2019**

The founding paper of index-time query generation. A sequence-to-sequence model trained on (query, relevant passage) pairs predicts queries each passage might answer; the predicted queries are appended to the passage text before BM25 indexing, so query-time matching becomes partly query-to-predicted-query. On MS MARCO dev, MRR@10 rises from **18.4 to 21.5** and Recall@1000 from **85.3% to 89.3%**; with a BERT re-ranker on top, MRR@10 reaches **37.5**. TREC-CAR MAP rises **15.3 → 18.3**. Query latency stays near BM25 (**50 → 90 ms/query**) because all neural inference is paid at index time. The T5 successor docTTTTTquery (Nogueira & Lin, 2019) scales the same recipe: **40 sampled queries per passage**, MRR@10 **27.2** on the leaderboard (dev table: 5 samples 25.9, 10 samples 26.5, 20 samples 27.2 - monotone but diminishing), at 64 ms/query.

**Key mechanism**
- Train seq2seq (transformer; later T5) on MS MARCO (query, passage) pairs to predict queries from passages
- Generate 10 queries per passage via top-k random sampling (docTTTTTquery: 40)
- Append generated query text to the document text; index the expanded document with plain BM25
- Expansion does two jobs: term re-weighting (69% of generated words copy existing document terms, boosting them) and vocabulary injection (31% are new terms, bridging the query-document lexical gap)

**Main findings**
- MS MARCO dev: MRR@10 18.4 → 21.5, Recall@1000 85.3% → 89.3%; +BERT reranker 37.5
- docTTTTTquery: MRR@10 27.2 with 40 queries/passage - the number of sampled queries is the main quality dial, with diminishing returns
- ~7x faster than a neural re-ranker (Duet v2, 650 ms) at competitive first-stage effectiveness
- Expansion helps recall most - it widens the candidate set the ranker sees

**Key takeaways**
- Query prediction at ingest is the original "move the LLM to index time" pattern: expensive inference once per document, zero extra model calls per query
- Both copied terms (re-weighting) and novel terms (expansion) contribute; the mechanism is robust even under bag-of-words matching
- Queries-per-document is an explicit budget knob with measured diminishing returns

**Tags**: #doc2query #DocumentExpansion #IndexTimeQueryGeneration #MSMARCO #BM25

**Source**: https://arxiv.org/abs/1904.08375 (docTTTTTquery report: https://cs.uwaterloo.ca/~jimmylin/publications/Nogueira_Lin_2019_docTTTTTquery-v2.pdf). Local: [paper] doc2query, 2019-04.pdf
