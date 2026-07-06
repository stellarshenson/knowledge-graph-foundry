# Small Language Model Can Self-Correct

**Source**: https://arxiv.org/abs/2401.07301
**Authors**: Haixia Han, Jiaqing Liang, Jie Shi, Qianyu He, Yanghua Xiao (ECNU / Fudan)
**Venue/Date**: AAAI 2024 (v2 May 2024)

## Summary

The paper introduces Intrinsic Self-Correction (ISC), a fine-tuning method that lets small language models (6B-13B) verify and revise their own answers in a single spontaneous step, without prompt-engineering pipelines or external critics. Across OpenBookQA and CommonsenseQA, ISC improves accuracy on all six tested models, with gains up to 5.6%.

## Method

- Self-correction data pipeline: an instruction-following LM generates COT answers, answers are checked against ground truth, and question-answer traces are formatted with self-verification and (when wrong) a corrected answer
- Single Self-Correction Prompt (SCP) triggers initial answer, self-verification, and self-modification as one comprehensive step (not separate calls)
- Partial Answer Masking (PAM): for "bad case" traces, the loss on the incorrect answer span is masked; only self-verification and the corrected answer contribute to gradient updates
- Fine-tuned via full fine-tuning, LoRA, or prompt-tuning depending on the base model (CuteGPT, Llama2-7B, ChatGLM-6B, Vicuna)

## Key Findings

- Accuracy improves on all six models; best case +5.6% (ChatGLM-6B on OpenBookQA, 37% -> 42.6%)
- PAM is essential: without it, self-verification accuracy collapses due to bad-case data imbalance
- Failure mode: high-confidence models (Vicuna family) rarely self-verify or correct
- W2R transitions confirm hallucination is partly contextual, not only knowledge gaps, so self-correction is feasible; ISC generalizes zero-shot to StrategyQA

## Relevance to KGF

- SUPPORTS H31 (small local model in a verify-repair loop): direct evidence that a small model can be trained to self-verify and self-repair its own output, the core mechanism behind preferring a small model in a verify-repair loop over a big single-pass model
- Caveat for H31: gains are modest (single-digit points) and blocked when the model is overconfident or lacks the underlying knowledge - a KGF loop would need external evidence grounding, not pure self-verification
- The verify-then-modify pattern maps onto KGF's re-extract-from-source repair step
