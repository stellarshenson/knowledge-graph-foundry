# Segment any Text (SaT) - universal robust sentence segmentation

**Frohmann et al., EMNLP 2024** - arXiv 2406.16678. Neural sentence/paragraph segmenter reaching **F1 84.9-93.1 averaged over 81-85 languages** (SaT 84.9, +supervised-mixture 91.6, +LoRA domain adaptation 93.1) vs WtP baseline 84.2 and Llama-3-8B 79.1, at **~3x the speed of prior SOTA** (~1,000 sentences / 0.5 s on an RTX 2080 Ti; CPU-capable, ONNX path ~50% faster than PyTorch).

**Key mechanism**: XLM-RoBERTa backbone predicts a per-token boundary (newline) probability; a threshold converts probabilities to splits. Because the training target is newline probability, the same model performs paragraph segmentation (`do_paragraph_segmentation=True`). Variants sat-1l..sat-12l trade speed for quality; `-sm` heads are trained on punctuation-corrupted mixtures for robustness.

**Main findings**: the margin over baselines widens exactly on noisy text - on corrupted sentence pairs SaT+LoRA reaches **81.8 macro F1 vs 58.2 for WtP** - the regime of PDF-extracted text with missing or mangled punctuation.

**Key takeaways for KGF**: drop-in upgrade for the regex sentence-boundary snapping in `chunking.py` (3-pattern `". "`/newline match); CPU inference means zero GPU cost; it is a boundary primitive, not a chunk-grouping policy - it addresses seam quality, not co-occurrence.

**Tags**: sentence-segmentation, chunking, boundary-detection, multilingual
**Source**: https://arxiv.org/abs/2406.16678 (PDF: `[paper] segment any text sat, 2024.pdf`) - code https://github.com/segment-any-text/wtpsplit
