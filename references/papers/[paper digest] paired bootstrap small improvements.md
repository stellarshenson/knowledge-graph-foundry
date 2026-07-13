# When +1% Is Not Enough: A Paired Bootstrap Protocol for Evaluating Small Improvements

**Authors**: Du Wenzhang (Mahanakorn University of Technology, MUTIC)

**arXiv link (source for re-download)**: https://arxiv.org/abs/2511.19794

**Publication date**: 2025-11 (arXiv preprint)

## Summary

- Targets the common ML reporting failure mode: a **+1-2 percentage point** single-run gain claimed as a real improvement with no seeds, no uncertainty estimate, no significance test
- Proposes a **PC-friendly, low-budget protocol**: paired multi-seed runs, **BCa (bias-corrected and accelerated) bootstrap confidence intervals**, and a sign-flip permutation test computed on per-seed deltas - deliberately conservative, framed as a guardrail against over-claiming
- Validated on CIFAR-10, CIFAR-10N, and AG News with synthetic no-improvement / small-gain / medium-gain scenarios
- With only **three seeds**, the paired protocol never declares significance where single-run and unpaired t-test analysis suggested significant gains for **0.6-2.0 point** improvements - especially on text tasks, where unpaired tests are shown to be most prone to false positives
- Argues conservative paired evaluation should be the default when compute is tight (few affordable seeds), not an optional extra step

**Relevance to Knowledge Graph Foundry**: a modern, directly reusable drop-in for KGF's frozen-probe paired A/B design - the paired-multi-seed-plus-BCa-bootstrap-plus-sign-flip-permutation combination is exactly the shape of gate H541/H543 already target, and the demonstrated failure of unpaired/single-run comparisons at KGF's typical delta scale (single-digit percentage points) is a live warning against any A/B verdict that skips pairing.

**Tags**: paired-bootstrap, bca, significance-testing, small-improvements, permutation-test, reproducibility

**Source**: https://arxiv.org/abs/2511.19794
