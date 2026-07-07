**OmniDocBench: Benchmarking Diverse PDF Document Parsing with Comprehensive Annotations**

The field's current reference benchmark for end-to-end document parsing (CVPR 2025), spanning **~981 curated PDF pages** (v1.0) across **9 document types**, bilingual **English + Chinese**, with **28 block-level** and **4 span-level** annotation categories. It scores parsers on four axes - text edit distance, formula (CDM), table structure (TEDS), and reading order - and is the leaderboard every 2024-2026 parser reports against. Critically, it grades page-level fidelity, not per-entity string recall.

**Key mechanism**
- Fine-grained ground truth: every text block, heading, table, formula, figure caption is annotated with region + reading order, enabling per-element scoring instead of a single blob-diff
- Table structure scored by **TEDS** (Tree-Edit-Distance Similarity) and **TEDS-S** (structure only, content ignored)
- Text scored by normalized edit distance (lower better); formulas by CDM; reading order by edit distance on the block sequence
- Splits results by language, table frame type (full-border / partial / borderless), and "special situations" (rotation, watermark, blur)

**Main findings**
- End-to-end table TEDS (EN / ZH): **MinerU 79.4 / 62.7** (best pipeline), Mathpix 77.9 / 68.2, GPT-4o 72.8 / 63.7, Qwen2-VL 59.9 / 66.8, GOT-OCR 53.5 / 48.0, Marker 54.0 / 45.8, Nougat 40.3 / 0.0
- Text edit distance EN: MinerU **0.058** (best), GPT-4o 0.144, Marker 0.141, GOT-OCR 0.187, Nougat 0.365
- Pipeline/OCR-based tools (MinerU, Mathpix) beat expert and general VLMs of the 2024 generation on overall structured fidelity; RapidTable strongest on pure table recognition across frame types
- Chinese and borderless tables are the universal weak point across every method

**Key takeaways**
- TEDS/edit-distance are page-fidelity proxies, not entity-name recall - a parser can score 90 TEDS and still drop a specific model number in a dense row
- Born-digital pipeline tools (MinerU) still lead 2024-era VLMs on tables; the VLM crossover only arrives with the 2025 specialist models (MinerU2.5, dots.ocr)

**Relevance** (honest, our corpus)
- Directly the yardstick for choosing a replacement/augment for pymupdf4llm, but its metric does not measure our failure mode (specific product-name strings in catalogue tables). Use rankings as a prior, then re-measure name-recall on our 27 docs - the two need not correlate. Benchmark is mostly clean single-column + some scanned pages, lighter on the dense multi-column catalogues that break our parser.

**Tags** #DocumentParsing #Benchmark #TableStructure #TEDS #OCR #BornDigital

**Source** https://arxiv.org/abs/2412.07626 - local: [paper] OmniDocBench, 2024.pdf
