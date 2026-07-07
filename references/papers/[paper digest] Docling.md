**Docling: An Efficient Open-Source Toolkit for AI-driven Document Conversion**

IBM's **MIT-licensed** PDF-to-Markdown/JSON toolkit (Aug 2024, updated 2025) built on two specialist models - **DocLayNet** layout analysis and **TableFormer** table structure - that runs on commodity CPU in a small budget. It is the strongest born-digital-friendly structured parser: it reuses the PDF's own programmatic text cells rather than re-transcribing pixels, which is both its speed advantage and its ceiling.

**Key mechanism**
- Linear pipeline: a **PDF backend** (default `docling-parse`, alt `pypdfium`) retrieves programmatic text cells + coordinates; layout model tags regions; TableFormer predicts table structure
- **TableFormer** receives an image-crop plus the enclosed text cells and predicts row/column/span structure; predictions are **matched back to the PDF text cells in post-processing to avoid expensive re-transcription** - so table *content* comes from the text layer, only *structure* is inferred
- IBM explicitly rejected **pymupdf** for its backend, citing "merged text cells" and unrecoverable quality issues - motivating their custom `docling-parse`
- OCR is optional/off by default (only engaged for scanned regions)

**Main findings**
- TableFormer: typical table processed in **2-6 s on a standard CPU**; IBM reports it outperforming leading table-recognition tools internally
- Corpus-scale timing (independent study): Docling **~9.5 h** vs Marker ~23.7 h vs Nougat ~16 h on the same set - fast for a structured parser
- On OmniDocBench (v2.14.0 entry) it is competitive among pipeline tools but below MinerU on tables
- Runs CPU-only; no GPU required

**Key takeaways**
- Because content is drawn from the text layer, Docling **cannot recover text that is absent from all text extractors** (the stylized/embedded-graphic family) - same blind spot as pymupdf4llm
- But its `docling-parse` backend fixes cell-merge/reading-order bugs that plague pymupdf4llm, so it can plausibly recover born-digital table names that our current parser drops - with zero GPU cost

**Relevance** (honest, our corpus)
- The cheapest, most direct swap to test against the **95 lost names**: if the loss is pymupdf4llm's cell-merging (not truly-missing glyphs), `docling-parse` should recover them on CPU. It will **not** touch the all-parser-absent family or lift the 67.3% numeric floor - those need the vision path. Best framed as "better text backend first, VLM only for the residue."

**Tags** #StructuredParser #Docling #TableFormer #BornDigital #TextLayer #CPUInference

**Source** https://arxiv.org/abs/2408.09869 - local: [paper] Docling, 2024.pdf
