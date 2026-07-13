**Information Retrieval System Evaluation: Effort, Sensitivity, and Reliability (2005)**

The paper asks a resource-allocation question that TREC-style evaluation had never settled empirically: given a fixed evaluation budget, is it better to judge more documents deeply for few topics (queries) or judge fewer documents across many topics? Using large TREC pool data, Sanderson and Zobel show that **topic-set size dominates judgment depth** - shallow pools across many topics produce more reliable system comparisons than deep pools across few topics, and comparisons run on **25 topics are frequently unreliable**, reversing under repeated resampling. The paper won the SIGIR Test of Time Award and reframed how test collections since have been budgeted.

**Key mechanism**
- Resampling experiment over existing large TREC judgment pools: repeatedly draw topic subsets of varying size (e.g. 25, 50) and re-run system-vs-system comparisons to measure how often the ranking flips
- Compares significance tests directly against each other - paired t-test, Wilcoxon signed-rank, and sign test - on the same resampled topic sets
- Measures "sensitivity" as the fraction of system pairs for which a test detects a significant difference, and "reliability" as consistency of that verdict across resamples
- Separately varies judgment-pool depth (how many documents per topic get a relevance judgment) to isolate the effort/topics tradeoff from the effort/depth tradeoff
- Reports where a large measured percentage difference in effectiveness between two systems still fails to be a statistically reliable difference

**Main findings**
- The paired t-test is the most reliable of the three tests compared, more reliable than Wilcoxon or sign test at equivalent topic-set sizes
- A large measured effectiveness gap between two systems (large % difference) is not a reliable indicator of a real difference - the significance test result is far more trustworthy than eyeballing the delta
- Comparisons run on the common **25-topic** subset regularly disagree with comparisons run on larger topic sets from the same pool, exposing 25 topics as an unreliable evaluation floor
- Increasing the number of topics judged is more effective at improving reliability than increasing judgment depth per topic for a fixed total judging effort

**Key takeaways**
- Topic-set size, not judgment depth, is the lever that buys evaluation reliability - a finding that reshaped TREC-era test collection design toward "more topics, shallower pools"
- A visually large score gap between two systems is not evidence of a real difference without a significance test behind it
- 25 topics is an established unreliable floor in the IR literature, not a project-specific guess - any benchmark run at that scale should expect result reversals under resampling

**Relevance**
- Directly justifies raising KGF's benchmark topic-set floor above 25 (H540 band re-pricing) - this paper is the primary literature source establishing 25 as unreliable and pointing toward 50+ as the reliability threshold

**Tags**
- #IRatiEvaluation
- #StatisticalReliability
- #TestCollections
- #SignificanceTesting

**Source**
- Download: https://web.archive.org/web/20240412025442/https://marksanderson.org/publications/my_papers/SIGIR2005.pdf
- Local: [paper] ir system evaluation effort sensitivity reliability, 2005.pdf
