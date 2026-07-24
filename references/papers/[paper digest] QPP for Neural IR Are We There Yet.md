**Query Performance Prediction for Neural IR: Are We There Yet? (Faggioli et al., ECIR 2023)**

Evaluates **19 query performance predictors (QPPs)** against **7 lexical (bag-of-words) and 7 BERT-based first-stage neural retrievers** on Robust'04 and DL'19, and finds QPP is **statistically significantly worse at predicting neural-IR performance than lexical-IR performance** - post-hoc score-based failure prediction breaks down exactly where retrieval has gone dense/semantic.

**Key mechanism**
- QPP taxonomy: pre-retrieval predictors (query/corpus statistics, e.g. IDF spread) vs post-retrieval predictors, the latter split into coherency-based (Clarity - divergence of top-doc language model from the collection), score-based (WIG, NQC, SMV - shape of the retrieval score distribution), and robustness-based
- Predictors estimate per-query effectiveness (AP/nDCG) with no relevance judgements, then are scored by correlation (Kendall/Pearson) with true per-query performance
- Includes supervised/semantic QPP (BERT-QPP) as a modern baseline

**Main findings**
- On DL'19 (where neural models learned the semantics) QPPs predict lexical systems well but **fail on neural systems**
- Passage retrieval / semantic-heavy settings: QPP accuracy on neural models drops by **up to 10%** vs bag-of-words
- QPPs fail precisely on the queries where neural and lexical rankings diverge most - i.e. they cannot flag the neural-specific failures that matter
- Semantic QPP (BERT-QPP) does not fix it: tuned on lexical systems, it works on lexical and still fails on neural
- Conclusion: existing score-distribution QPP does not transfer to dense retrieval; neural-tailored predictors are still needed

**Key takeaways**
- Score-shape signals (WIG/NQC/SMV = the shape and gap of the top-k score distribution) are weak per-query failure predictors for dense/semantic retrieval - the field's own verdict, not a KGF idiosyncrasy

**Relevance to KGF atlas (R57)**
- Directly **validates our three KILLED score-shape confidence attempts**: post-hoc, score-distribution-based per-query failure prediction is empirically weak for neural retrieval, and worst on exactly the semantically-hard queries. The literature agrees the score-shape axis is closed for dense IR - our kills are consistent with SOTA, not a local failure
- Implication for the **dense axis**: signed-distance-to-cutoff is fine as a descriptive miss coordinate (post-mortem) but the paper warns it should not be promoted to a predictive confidence signal - the exact trap our kills fell into
- Extends the atlas's honesty boundary: QPP separates pre-retrieval predictors (query/corpus stats) from post-retrieval (score shape); our atlas is entirely post-retrieval. A **pre-retrieval / query-side predictor** (query specificity, anchor IDF) is the untried lever the QPP split points at, complementing the closed score-shape axis

**Tags**: query-performance-prediction, qpp, score-distribution, neural-ir, per-query-failure, confidence-prediction

**Source**: https://arxiv.org/abs/2302.09947
