# Statistical Significance Testing in Information Retrieval: An Empirical Analysis of Type I, Type II and Type III Errors

**Authors**: Julian Urbano, Harlley Lima, Alan Hanjalic (TU Delft)

**arXiv link (source for re-download)**: https://arxiv.org/abs/1905.11096

**Publication date**: 2019-05 (SIGIR 2019)

## Summary

- Settles the which-test question for paired system comparisons by SIMULATION with a known null - stochastically generates realistic system-pair score distributions so actual Type I / II / III error rates are measurable, instead of split-half discordance proxies on the same 50 topics
- Grid: 5 paired tests (t-test, Wilcoxon, sign, bootstrap-shift, permutation) x 4 measures (AP, nDCG@20, ERR@20, P@10/RR) x topic-set sizes **25 / 50 / 100** x effect sizes
- **The paired t-test wins**: maintains Type I exactly at alpha across all measures and sizes, is the most powerful (especially at small n), is remarkably robust to non-normality, and is simpler than the alternatives; the permutation test behaves near-identically and remains useful for non-mean statistics
- **Discontinue**: Wilcoxon and sign tests (unreliable), bootstrap-shift (systematic bias toward small p-values → Type I inflation, only partly cured by large samples)
- **Type III errors** (significant result, wrong direction) reach **~2%** for P@10/RR at small topic sets - directional conclusions from small probe sets on shallow metrics carry a real wrong-sign risk

**Relevance to Knowledge Graph Foundry**: the license to standardize every A/B verdict on ONE test form - the paired t-test on per-question deltas (Welch variant when arms have unequal run counts, as H351 already registered). No zoo of tests, no bootstrap gates. The Type III finding is a direct warning for KGF's 24-probe scale: at n = 24 with binary-ish per-probe scores, a "significant" delta can be significant in the WRONG DIRECTION ~2% of the time - another count against gating on the saturated harness. Topic-set-size results reinforce the Error Bars arithmetic: 25-100 questions resolve only coarse effects.

**Tags**: statistics, significance-testing, paired-t-test, type-iii-errors, ir-evaluation, test-selection
