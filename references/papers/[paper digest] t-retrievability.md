**T-Retrievability: A Topic-Focused Approach to Measure Fair Document Exposure**

This 2025 paper (arXiv 2508.21704) proposes **T-Retrievability**, computing retrievability scores within topically-related document groups first, then aggregating to the collection level - arguing that a single collection-wide r(d) distribution conflates true exposure bias with ordinary topical relevance variation.

**Key mechanism**: Standard retrievability is a collection-based statistic - the expected reciprocal rank of a document being retrieved within a rank cutoff, aggregated over a large query set. T-Retrievability instead partitions the collection into topic clusters, computes localized r(d) scores within each cluster, then rolls the per-topic distributions up into collection-level statistics - separating "this document is under-exposed because the system is biased" from "this document is under-exposed because it's off-topic for most queries."

**Main findings**:
- Collection-wide retrievability distributions can misattribute topical relevance skew to system exposure bias, producing a distorted fairness picture
- T-Retrievability applied to several neural ranking models reveals exposure patterns invisible to the global measure - some models that look fair globally show concentrated unfairness within specific topic clusters, and vice versa
- The topic-localized approach gives a more reliable, more actionable signal for auditing which topic areas a ranking model systematically under-serves

**Key takeaways (relevance to KGF)**: Provides the direct template for scoping fact-retrievability to its own anticipated-question cluster rather than the whole corpus - a fact-carrier's retrievability should be measured against the topic/question-space it actually belongs to, not diluted by unrelated topic traffic. This guards against a KGF health metric mistaking "this fact answers a rare question type" for "this fact is unfairly buried," mirroring the paper's core distinction between topical relevance and true exposure bias.

**Tags**: retrievability, topic-focused, exposure-fairness, neural-ranking, arXiv-2025

**Source**: https://arxiv.org/abs/2508.21704
