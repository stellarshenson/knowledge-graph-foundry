**MinerU2.5: A Decoupled Vision-Language Model for Efficient High-Resolution Document Parsing**

A **1.2B-parameter** document-parsing VLM (Shanghai AI Lab, Sep 2025) that posts **90.67 overall on OmniDocBench**, beating dots.ocr (88.41), MonkeyOCR-pro-3B (88.85), and general models 10-60x its size (Qwen2.5-VL-72B ~87, GPT-4o, Gemini-2.5-Pro). It is the current open-weight SOTA for born-digital-and-scanned parsing at a size that runs comfortably on a single 24GB card, and it is pure-vision (reads pixels, no PDF text-layer anchoring).

**Key mechanism**
- Decoupled coarse-to-fine, two-stage: stage 1 does layout analysis on a **downsampled** page; stage 2 does content recognition on **native-resolution crops** guided by the stage-1 layout
- 675M NaViT-style visual encoder + 500M language decoder; handles high-res pages without exploding token count
- Emits Markdown/HTML with tables, formulas (LaTeX), reading order in one model; no separate detector/OCR pipeline
- Trained on large curated doc corpus; specialist heads for table and formula tokens

**Main findings**
- OmniDocBench **90.67** overall; strong table and formula sub-scores driving the win
- Throughput: **2.12 PDF pages/s on A100**, **1.70 pages/s on RTX 4090**, 4.47 on H200, vs 0.95 unoptimized baseline; **4x faster than MonkeyOCR-pro-3B, 7x faster than dots.ocr**
- olmOCR-Bench 75.2 overall (arXiv-Math 76.6, Old-Scans-Math 54.6) - weaker on degraded scans than on clean pages
- Ocean-OCR edit distance EN 0.033 / ZH 0.082

**Key takeaways**
- Best accuracy-per-VRAM in the open field; 1.2B fits the RTX PRO 4000 (24GB) with room to spare and hits ~1.7-2 pages/s
- Pure-vision path means it can, in principle, read stylized/embedded-graphic text that no text extractor sees - unlike anchoring-based olmOCR

**Relevance** (honest, our corpus)
- Top candidate to re-parse the table-heavy catalogues and, uniquely, to attack the all-parser-absent product-name family (it reads glyphs from pixels). Caveat: OmniDocBench score does not certify recall of specific dense-table product strings, and VLM parsers can hallucinate plausible-but-wrong model numbers - name precision must be checked, not assumed. Local, MIT-adjacent, no cloud.

**Tags** #VisionLLM #DocumentParsing #MinerU #TableStructure #LocalInference #SOTA

**Source** https://arxiv.org/abs/2509.22186 - local: [paper] MinerU2.5, 2025.pdf
