**SIGIR 2004 Workshop: RIA and "Where can IR go from here?" (Harman & Buckley, 2004)**

Reports the **Reliable Information Access (RIA) Workshop** failure analysis - a manual, per-topic autopsy of **six top research IR systems across 45 TREC topics** - the canonical study of *why* IR systems fail per query, and the origin of Buckley's failure-category lineage ("Why current IR engines fail", SIGIR 2004 poster).

**Key mechanism**
- Each of six systems contributed one representative run; for each of 45 topics, humans manually inspected the run and its retrieved documents to diagnose the root cause of poor performance
- Failure attributed to topic factors (the question statement) vs system factors, with the analysis isolating which aspect of the topic the top documents fail to reflect
- Buckley's companion poster categorizes the observed failures (general technique failures; emphasizing one aspect while missing another; missing a hard aspect; expansion emphasizing the wrong aspect)

**Main findings**
- **The root cause of poor performance on a topic is the same across all systems** - except for 6 of 45 topics, all systems fail for the same reasons (to differing extents)
- Systems retrieve largely different documents from each other, yet **all miss the same topic aspect** in their top documents - failure is a property of the topic, not the system
- For well over half the failing topics, current technology could fix the result *if the system could recognize which problem the topic poses* - the research lever is matching known techniques to topics, not inventing new ones
- "Despite many efforts no one knows how to choose good approaches on a per-topic basis" - per-query technique selection / failure prediction is the standing hard problem

**Key takeaways**
- Retrieval failure is largely **systematic and topic-intrinsic**, not random per-system noise - the same aspect is missed regardless of ranker
- The field's long-standing verdict: diagnosing a failure post-hoc is tractable, but *predicting/selecting the fix per query in advance* has resisted decades of effort

**Relevance to KGF atlas (R57)**
- Answers Question (B): classic IR failure analysis converged on per-topic categories (missed-aspect being dominant), and independently reached the same conclusion as our killed score-shape axis - **per-query failure prediction is hard**, validating (not contradicting) our closed axes from a pre-neural angle
- "All systems miss the same aspect" grounds the atlas's ambition: because the miss is topic-intrinsic, a per-(probe,entity) coordinate system is meaningful - the miss will reproduce across retriever variants, so the atlas is measuring structure, not run-to-run luck
- Supports the atlas's **one-class-per-miss partition** claim: RIA found failures cluster into a small set of root-cause categories dominated by a single missed aspect per topic - a partition, echoing our aspiration, but warns the categories overlap in practice ("to differing extents") - a strict single-class-per-miss partition may be too clean
- The "match technique to topic, don't invent new ones" lesson maps to KGF's use-case-regime doctrine: the lever is routing the right retrieval treatment (anchor-reset, escalation) to the diagnosed miss class, i.e. the atlas as a router input

**Tags**: ir-failure-analysis, ria-workshop, per-query-prediction, missed-aspect, buckley, topic-intrinsic-failure

**Source**: https://sigir.org/files/forum/2004D/harman_sigirforum_2004d.pdf (companion: C. Buckley, "Why current IR engines fail", SIGIR 2004, pp. 584-585)
