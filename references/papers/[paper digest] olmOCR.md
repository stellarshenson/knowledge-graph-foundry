**olmOCR: Unlocking Trillions of Tokens in PDFs with Vision Language Models**

AI2's open OCR toolkit (Feb 2025) built on a fine-tuned **7B VLM** (Qwen2-VL-7B; olmOCR-2 upgrades to Qwen2.5-VL-7B) that converts **a million PDF pages for ~\$176** versus \$6,240 for GPT-4o - a ~35x cost drop. Its defining idea, **document-anchoring**, injects the born-digital PDF's own text layer into the prompt, which is exactly the double-edged property to watch for our corpus.

**Key mechanism**
- **Document-anchoring**: uses **pypdf** to extract the page's existing text blocks and their coordinates, then feeds ~1,800 tokens of that anchor text alongside the ~1,000-token rendered page image (~2,800 tokens/page)
- The VLM is prompted to reconcile the rendered pixels with the anchor text and emit clean reading-ordered Markdown
- olmOCR-2 adds unit-test / RL-style rewards on 270k pages; FP8 weights enable fast serving
- Runs as a local vLLM batch pipeline on a single GPU

**Main findings**
- olmOCR-2 scores **82.4 on olmOCR-Bench** (7k+ test cases, 1,400 docs), ~4 pts over v1
- Throughput: **3,400 output tokens/s on one H100** (FP8), ~10,000 pages for under \$2; ~\$176 per million pages
- 7B in bf16 ~ 16-18GB VRAM (fits 24-32GB cards); FP8 lower
- Optimized for real-world scanned/print OCR accuracy, not specifically dense born-digital catalogues

**Key takeaways**
- Cheapest local vision-LLM OCR at scale; runs on our idle 24/32GB cards
- The anchoring trick is the catch: on **born-digital** pages the anchor text is the same pypdf/text-layer output that already drops our names, so anchored olmOCR can **inherit the exact losses** unless the image signal overrides them - image-only mode is the honest test

**Relevance** (honest, our corpus)
- Attractive on cost, but document-anchoring makes it the least obviously-helpful vision path for our specific failure: it re-reads the text layer we already know is lossy. For the all-parser-absent family, only its image branch can help, and default anchoring may suppress that. Prefer pure-vision parsers (MinerU2.5, dots.ocr) for the absent-name family; keep olmOCR as the cheap bulk-throughput option and A/B anchor-on vs anchor-off.

**Tags** #VisionLLM #OCR #DocumentAnchoring #LocalInference #BornDigital #CostEfficient

**Source** https://arxiv.org/abs/2502.18443 - local: [paper] olmOCR, 2025.pdf
