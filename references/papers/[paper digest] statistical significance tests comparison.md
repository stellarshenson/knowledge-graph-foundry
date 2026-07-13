# A Comparison of Statistical Significance Tests for Information Retrieval Evaluation

**Authors**: Mark D. Smucker, James Allan, Ben Carterette (University of Massachusetts Amherst, CIIR)

**Source (for re-download)**: https://ciir-publications.cs.umass.edu/getpdf.php?id=744

**Publication date**: 2007 (CIKM 2007, Lisboa)

## Summary

- Runs all five candidate paired tests (Student's t-test, Wilcoxon signed-rank, sign test, bootstrap, Fisher's randomization/permutation) on every pair of ad-hoc retrieval runs submitted to **TRECs 3 and 5-8**, measuring significance of mean average precision differences
- **Randomization, bootstrap, and t-test agree closely** with each other - little practical difference between the three across thousands of run pairs
- **Wilcoxon and sign tests are the outliers**: both show poor power to detect real significance and carry a real risk of false detections; the paper frames them as simplified (degraded) variants of the randomization test
- Explicit recommendation: **discontinue Wilcoxon and sign tests** for comparing IR system means; use t-test, randomization, or bootstrap instead
- A handful of run pairs show the t-test's normality assumption producing visibly larger p-values (0.17-0.22) than randomization/bootstrap (~0.07-0.1) - a rare but real divergence case, not the general pattern

**Relevance to Knowledge Graph Foundry**: direct historical backing for H541 - confirms from TREC-scale empirical data (not simulation) that paired randomization, bootstrap, and t-test are the correct family for IR-style paired comparisons, while Wilcoxon/sign should not be used. Predates and agrees with the Urbano et al. 2019 SIGIR simulation study already in this library, giving two independent lines of evidence (real TREC runs here, simulated null distributions there) for the same test-selection verdict feeding KGF's A/B gating design.

**Tags**: statistical-significance, ir-evaluation, paired-tests, wilcoxon, bootstrap, randomization-test, trec

**Source**: https://ciir-publications.cs.umass.edu/getpdf.php?id=744
