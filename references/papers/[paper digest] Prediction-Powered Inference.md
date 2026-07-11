# Prediction-Powered Inference

**Authors**: Anastasios N. Angelopoulos, Stephen Bates, Clara Fannjiang, Michael I. Jordan, Tijana Zrnic (UC Berkeley)

**arXiv link (source for re-download)**: https://arxiv.org/abs/2301.09633

**Publication date**: 2023-01 (v4 2023-11; Science 2023)

## Summary

- Framework for **provably valid confidence intervals** on means, quantiles, and regression coefficients when a small gold-labeled dataset (n) is supplemented by a large dataset (N) labeled only by ML predictions - **no assumptions on the ML system**
- Mechanism: the **rectifier** - measure the prediction's bias on the gold-labeled subset, subtract it from the imputed estimate, and widen the interval by the rectifier's own uncertainty; more accurate predictions → smaller intervals, but validity never depends on accuracy
- Strictly dominates the two naive poles: the imputation approach (trust predictions, invalid when biased) and the classical approach (ignore predictions, wide intervals from scarce labels)
- Demonstrated on AlphaFold proteomics, astronomy, genomics, remote sensing, census and ecology datasets - CI width reductions equivalent to multiplying the gold-label budget several-fold when predictions are good
- ARES (arXiv 2311.09476) is the direct RAG-evaluation application: LLM judge = prediction system, ~150-300 human labels = gold set

**Relevance to Knowledge Graph Foundry**: the statistical engine that turns a cheap noisy instrument (LLM judge, heuristic matcher, embedding-similarity check) into a calibrated one. KGF's pattern: run the cheap judge on ALL items (1000-question benchmark, every extracted fact), adjudicate a fixed ~150-300 sample once, and report PPI intervals - judge bias is subtracted rather than hoped away. Composes with the H389 coverage certificate (LLM support-test = prediction, human-verified miss sample = gold) and with any R42 faithfulness metric. This is variance-pricing for judge noise, the same H351 doctrine applied to instrument error instead of run-to-run error.

**Tags**: statistics, confidence-intervals, semi-supervised-inference, llm-judge-calibration, label-efficiency, rectifier
