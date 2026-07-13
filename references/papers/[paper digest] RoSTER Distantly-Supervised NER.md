# RoSTER: Distantly-Supervised NER with Noise-Robust Learning and Language Model Augmented Self-Training

**Authors**: Yu Meng, Yunyi Zhang, Jiaxin Huang, Xuan Wang, Yu Zhang, Heng Ji, Jiawei Han (University of Illinois Urbana-Champaign)

**arXiv link (source for re-download)**: https://arxiv.org/abs/2109.05003

**Publication date**: 2021-09-10

## Summary

- Trains NER purely from distant labels (entity-mention matches against Wikidata + gazetteers via SPARQL) with zero human annotation, and still closes most of the gap to fully supervised RoBERTa: F1 **85.4 CoNLL03, 77.1 OntoNotes5.0, 67.8 Wikigold** - versus supervised RoBERTa's 91.2 / 88.8 / 86.4 and versus the best prior distantly-supervised baseline BOND's 81.5 / 73.6 / 60.0
- Distant-label quality is the floor being climbed from: raw Distant Match F1 is only 71.4 / 71.8 / 47.8 on the three sets, confirming the labels are both incomplete (missed mentions) and noisy (wrong types)
- RoSTER's F1 on CoNLL03 is reported equivalent to training supervised RoBERTa on roughly 1,000 cleanly annotated sequences - a concrete estimate of what the noise-robust + self-training pipeline buys over raw distant supervision
- Two-stage design: (1) noise-robust learning - generalized cross entropy (GCE) loss plus a threshold-based noisy-label-removal step that drops tokens where the model's own prediction disagrees with the distant label (fi,yi(x;theta) <= tau), then a 5-model ensemble distilled via KL divergence for stability; (2) self-training - the ensemble model is fine-tuned further on all tokens (including ones stripped by noisy-label removal) using its own high-confidence predictions as soft labels, with consistency enforced against LM-generated masked-and-resampled ("contextualized") augmentations of the same sentences
- Ablation on CoNLL03 (Table 3): removing GCE drops F1 to 0.830, removing noisy-label removal drops to 0.833, removing self-training drops to 0.828, versus 0.854 full - each component contributes independently and none is redundant
- Ensembling 5 independently-seeded models (before self-training) raises mean F1 from 0.817 to 0.828 and cuts run-to-run std from 0.025 to 0.009 - the main lever against training-instability noise, not just labeling noise
- Hyperparameters q and tau (both 0.7 by default) are shown insensitive across the 0.5-0.9 range and held fixed across all three datasets, i.e. no per-dataset tuning required

## Key mechanism

RoSTER treats distant labels as majority-correct-but-noisy rather than ground truth. The generalized cross entropy loss (GCE, a q-order interpolation between CE and MAE) down-weights tokens whose predicted probability under the given label is low, since CE's gradient over-weights exactly those disagreeing tokens while MAE treats all tokens equally but converges poorly - GCE splits the difference. Noisy-label removal then goes one step further: once the GCE-trained model's own prediction on a token falls below threshold tau against its distant label, that token is excluded from the loss entirely rather than just down-weighted, on the premise that a model dominated by the correct majority will disagree specifically with the wrong labels. Self-training then recovers the tokens dropped or under-used by the removal step: the ensemble model's current predictions are squared and renormalized into sharpened "soft labels" (Eq. 8, following Xie et al. 2016), and the model is retrained via KL divergence to match those soft labels on both the original sentence and a masked-then-MLM-resampled paraphrase of it - forcing prediction consistency across surface variation while bootstrapping on tokens that had no reliable distant label at all.

## Main findings

- Main results table (precision / recall / F1), distantly-supervised methods only: Distant Match 0.811/0.638/0.714 (CoNLL03), Distant RoBERTa 0.837/0.633/0.721, AutoNER 0.752/0.604/0.670, BOND 0.821/0.809/0.815, RoSTER 0.859/0.849/0.854
- On OntoNotes5.0 (18 entity types, the most fine-grained of the three sets), RoSTER's recall (0.789) is the highest among distantly-supervised methods even though its precision (0.753) trails BOND's (0.774) - the self-training step recovers coverage the distant labels missed
- On Wikigold (smallest set, 1,142 train / 274 test sequences), RoSTER's margin over BOND is largest: F1 0.678 vs 0.600, precision +0.115, recall +0.024 - the noise-robust + self-training combination generalizes better than BOND's teacher-student self-training when in-domain distant-label volume is low
- Fully supervised ceiling (ground truth training data): BiLSTM-CNN-CRF 0.912/0.887/0.549 F1 and RoBERTa 0.912/0.888/0.864 F1 across the three sets - RoSTER closes most of the CoNLL03/OntoNotes5.0 gap but a substantial gap remains on Wikigold, where supervised RoBERTa still leads by 18.6 F1 points
- Dataset scale: CoNLL03 (4 types, 14,041 train / 3,453 test), OntoNotes5.0 (18 types, 59,924 train / 8,262 test), Wikigold (4 types, 1,142 train / 274 test)

## Key takeaways

- The paper's core claim - that a noise-robust loss plus threshold-based label removal plus self-training can recover most of a fully-supervised ceiling from incomplete, noisy distant labels - is the external, single-pass NER analogue of KGF's graph-as-lexicon hypothesis (H248, R47-H505): a growing dictionary or gazetteer plus high-recall self-training heals the incomplete-labeling misses that any one noisy extraction pass leaves behind, without requiring hand-labeled ground truth
- The self-training mechanism specifically targets the KGF failure mode of interest: tokens/entities a single pass either mislabels or fails to label are recovered not by re-running the same noisy labeler harder, but by bootstrapping on the model's own high-confidence output once enough signal has accumulated - directly analogous to using an already-materialized graph as reinforcing context for later extraction passes rather than treating each document in isolation
- The noisy-label-removal step (drop tokens where the model disagrees with the distant label, rather than force-fit) is the extraction-side mirror of KGF's coverage-loss/gap-ledger discipline: disagreement is treated as an abstention signal, not swallowed as ground truth
- The model-ensemble result (F1 std 0.025 to 0.009 with K=5) is a reminder that some of the variance KGF also fights (H107 extraction variance) is inherent to stochastic neural training, not solely a labeling-quality problem - ensembling is a distinct lever from noise-robust loss design
- Caveat: RoSTER operates purely at the token-classification level with a fixed, closed label space (from the distant KB/gazetteer); it does not address entity resolution, relation extraction, or open-schema typing, so the transfer to KGF is at the level of the recovery mechanism (self-training against a growing reference source), not the architecture

## Tags

`distant-supervision` `named-entity-recognition` `noise-robust-learning` `self-training` `generalized-cross-entropy` `data-augmentation` `RoBERTa` `NLP`

## Source

https://arxiv.org/abs/2109.05003
