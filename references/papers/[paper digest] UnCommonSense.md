# UnCommonSense: Informative Negative Knowledge about Everyday Concepts

**Authors**: Hiba Arnaout, Simon Razniewski, Gerhard Weikum, Jeff Z. Pan
**Published**: August 2022, CIKM 2022, arXiv:2208.09292
**Original**: https://arxiv.org/abs/2208.09292
**Local copy**: `[paper] UnCommonSense, 2022-08.pdf`

## Problem

Commonsense KBs store only positive assertions; salient negations ("penguins cannot fly") are absent, so downstream consumers cannot distinguish unknown from false.

## Mechanism

- **Local closed-world assumption over comparable concepts**: for a target concept, collect highly similar sibling concepts; assertions that hold for the siblings but are absent for the target become candidate negations
- Candidates are scrutinized (LM plausibility, corpus checks) then ranked by informativeness
- Output: curated, ranked negative statements per concept

## Results

Higher-quality negations than open-ended LM generation baselines on samples of everyday concepts; released dataset of informative negations.

## Relevance to KGF

The comparability-group mechanism is exactly R04-H23's gap generator: sibling devices carry `dimensions`, the target does not, so "SleepStyle 200 lacks recorded dimensions" is generated as a candidate gap. KGF then diverges: instead of publishing the negation, it first attempts repair-from-source; only if the corpus genuinely lacks the fact does the negation persist in the gap ledger - where it becomes the structural refusal signal for unanswerable questions.
