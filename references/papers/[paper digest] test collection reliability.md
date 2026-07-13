# On the Measurement of Test Collection Reliability

**Authors**: Julián Urbano, Mónica Marrero (Universidad Carlos III de Madrid), Diego Martín (Universidad Politécnica de Madrid)

**Source (for re-download)**: http://julian-urbano.info/files/publications/055-measurement-test-collection-reliability.pdf

**Publication date**: 2013 (SIGIR 2013, Dublin)

## Summary

- Reframes test-collection reliability using **Generalizability Theory (G-theory)**: a G-study estimates ANOVA variance components from a fully-crossed system x query design - variance from real system differences (σ²ₛ), query difficulty (σ²q), and system-query interaction (σ²ₛ:q) - then a D-study projects reliability indicators for a different (e.g. larger or smaller) number of queries
- Empirically ties G-theory's abstract reliability coefficients to a practitioner-legible metric by regressing them against **Kendall tau rank correlation** across data from **over 40 TREC collections**, closing the interpretability gap that made G-theory hard to act on before this paper
- Shows reliability indicators are **extremely sample-dependent**: the number of queries required to hit a target reliability level can swing by **orders of magnitude** depending on which systems and queries are sampled
- Introduces confidence intervals around the reliability statistics themselves, a more honest tool than a single point estimate for judging whether a collection is "reliable enough"
- Headline conclusion: the field's default of **50 topics is insufficient** even for stable system rankings, across the TREC collections surveyed

**Relevance to Knowledge Graph Foundry**: this is the source framework for H543 - G-theory variance decomposition plus D-study probe-count sizing gives KGF a principled way to ask "how many probes does the frozen benchmark need before an A/B verdict is trustworthy" instead of guessing at 24 or 63. The orders-of-magnitude sensitivity finding is a direct caution against treating KGF's current probe count as self-evidently adequate, and pairs with the Type III error findings in the Urbano 2019 digest already in this library (same first author, same research program).

**Tags**: generalizability-theory, test-collection-reliability, d-study, kendall-tau, trec, probe-sizing

**Source**: http://julian-urbano.info/files/publications/055-measurement-test-collection-reliability.pdf
