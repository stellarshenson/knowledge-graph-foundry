**PubTables-1M: Towards Comprehensive Table Extraction From Unstructured Documents (Table Transformer / TATR)**

Microsoft's foundational table-extraction dataset and models (2021), releasing **~948k tables** from born-digital scientific PDFs (PMC) with detailed structure, header, and location ground truth, plus two **DETR** models - one for table detection, one for structure recognition ("Table Transformer", TATR). It anchors the table-structure lineage that TableFormer and the 2025 successors extend.

**Key mechanism**
- Two object-detection transformers (DETR): table detection locates table regions; table structure recognition predicts rows, columns, spanning cells, and header roles
- Introduced **canonicalization** to remove oversegmentation/annotation noise and the **GriTS** metric for structure evaluation (complementing PubTabNet's TEDS)
- Born-digital by construction: cell text is read from the PDF layer; the model supplies geometry/structure, then text is snapped to detected cells

**Main findings**
- ~948k fully-annotated tables; near-1M scale enabled the first robust general table-structure transformer
- DETR-based structure recognition became the reference baseline that pipeline parsers (incl. TableFormer in Docling) build on
- 2025 successors on PubTabNet push structure fidelity to TEDS-S ~97-98 (e.g. TFLOP, UniTable, SPRINT), showing the sub-task is largely "solved" on clean scientific tables
- Weakest on borderless/partial-border and heavily-merged catalogue tables - the frame types our corpus is full of

**Key takeaways**
- Table structure recognition is a mature, high-scoring sub-task on clean born-digital tables, and is already **subsumed** inside Docling (TableFormer) and MinerU - we do not need a standalone TATR stage
- The residual failures live exactly where our corpus does: dense, irregular, borderless product tables - so a high PubTabNet TEDS is not evidence it will hold our specific names

**Relevance** (honest, our corpus)
- Confirms the "buy, don't build" call: any modern structured parser already carries a strong table-structure model, so our gap is not missing structure recognition - it is text-layer content loss and reading order. TATR-lineage models operate on the PDF text layer, so they share the all-parser-absent blind spot; they cannot recover glyphs that no extractor sees. Useful as background, not as a tool to deploy.

**Tags** #TableStructure #DETR #PubTables1M #GriTS #TEDS #BornDigital #Background

**Source** https://arxiv.org/abs/2110.00061 - local: [paper] Table Transformer PubTables-1M, 2021.pdf
