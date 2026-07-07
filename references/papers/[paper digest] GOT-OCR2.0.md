**General OCR Theory: Towards OCR-2.0 via a Unified End-to-end Model (GOT-OCR 2.0)**

A **580M-parameter** end-to-end OCR VLM (Sep 2024) that folds document text, formulas, tables, charts, and scene text into a single image-to-markup model running in **~4-8.5GB VRAM**. It defined the "OCR-2.0" framing (one model, pixels to structured markup) but predates the 2025 specialists and is notably weak on complex tables.

**Key mechanism**
- Compact vision encoder + lightweight decoder trained end-to-end to emit Markdown/LaTeX directly from a page image - no separate detector, layout model, or text-recognition stage
- Pure-vision: reads glyphs from pixels, so it is independent of any PDF text layer
- Supports region-prompt and multi-page modes; strong specialization on mathematical/LaTeX notation

**Main findings**
- Tiny footprint: 580M params, single consumer GPU (~4GB typical, ~8.5GB for best settings)
- OmniDocBench table TEDS **53.5 EN / 48.0 ZH** - well below MinerU (79.4) and 2025 VLMs (dots.ocr 88.6); text edit distance 0.187 EN
- Formula CDM 81.8 EN - among the best in the 2024 cohort for equations
- Higher latency than modular pipelines on complex layouts; trades speed for unified coverage

**Key takeaways**
- Excellent formula/scene-text recall for its size, but its table structure is too weak to be the primary tool for catalogue tables
- Value as a pure-vision reader of stylized text is real, but 2025 models (MinerU2.5, dots.ocr) dominate it on every axis relevant to us at only modestly higher cost

**Relevance** (honest, our corpus)
- Marginal for our table-heavy failure mode - its table TEDS is the weakest of the vision candidates. Only interesting as an ultra-light probe for the stylized/embedded-graphic name family on hardware far smaller than ours; given the idle 24/32GB cards, MinerU2.5 or dots.ocr strictly dominate it. Include as a baseline, not a contender.

**Tags** #VisionLLM #OCR2 #UnifiedModel #Formula #TableWeak #LowVRAM

**Source** https://arxiv.org/abs/2409.01704 - local: [paper] GOT-OCR2.0, 2024.pdf
