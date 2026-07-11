# Adding Error Bars to Evals: A Statistical Approach to Language Model Evaluations

**Authors**: Evan Miller (Anthropic)

**arXiv link (source for re-download)**: https://arxiv.org/abs/2411.00640

**Publication date**: 2024-11-01

## Summary

- Treats an eval as a SAMPLE from a question super-population and imports the experiment-design toolkit; five prescriptions: (1) CLT standard errors on every reported score, (2) clustered SEs when questions share a source document - naive SEs are **up to 3x too small** on real evals with clustered questions, (3) variance reduction by resampling answers K times and by scoring next-token probabilities instead of sampled tokens, (4) **paired differences** for model comparisons - Var(paired) = Var(unpaired) - 2 Cov(s_A, s_B)/n, a free variance reduction whenever scores correlate across questions, (5) power analysis before running
- The sample-size formula (paired, K resamples): **n = (z_a/2 + z_b)^2 (w^2 + s_A^2/K_A + s_B^2/K_B) / d^2** where w^2 = Var(x_A) + Var(x_B) - 2Cov(x_A, x_B)
- Worked example: detecting d = 0.03 at 80% power, alpha 0.05, typical paired variance w^2 = 1/9 → **n ~ 969 questions**; the paper's headline: "new evals should contain at least 1,000 questions"
- Inverting for fixed n gives the Minimum Detectable Effect: at n = 198 with resampling K raised 1 → 10, MDE drops **13.2% → 7.5%** - resampling buys resolution without new questions
- Bootstrap SEs are fine but unnecessary; Bernoulli-formula SEs are wrong for non-binary or clustered scores

**Relevance to Knowledge Graph Foundry**: the single most load-bearing source for R42 - it derives exactly the arithmetic KGF's instrument crisis needs. Direct consequences: the #59 benchmark's 1000-question sets natively resolve ~3-point deltas (MDE = 2.80 sqrt(w^2/n) = 0.0295 at w^2 = 1/9); a 1-point delta needs ~8,700 questions OR pairing/resampling that shrinks w^2; the 24-probe harness at run-mean sigma 0.029 (H351) can never see small levers regardless of statistics. Clustered SEs matter because KGF questions cluster by source document. The paired-difference identity is the formal statement of the mission's "difference out shared variance" requirement.

**Tags**: statistics, power-analysis, sample-size, paired-design, clustered-standard-errors, variance-reduction, eval-methodology
