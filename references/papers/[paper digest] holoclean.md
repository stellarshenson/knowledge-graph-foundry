**HOLOCLEAN: HOLISTIC DATA REPAIRS WITH PROBABILISTIC INFERENCE (2017)**

HoloClean unifies two previously separate data-repair traditions - constraint-based cleaning (integrity constraints, denial constraints) and statistics-based cleaning (value co-occurrence, external dictionaries) - into a single probabilistic program compiled automatically from the dataset and its constraints. Across a diverse set of real-world datasets with different error types, HoloClean reaches **~90% average precision and ~76% average recall**, an average F1 more than **2x better** than prior state-of-the-art repair methods, which the authors independently benchmark at F1 below 0.35 when using only one signal type.

**Key mechanism**
- Compiles integrity constraints, denial constraints, and external reference data into a probabilistic graphical model (factor graph) over candidate cell repairs
- Combines qualitative signals (which values violate a constraint) with quantitative signals (statistical co-occurrence patterns in the clean portion of the data) as joint evidence for the correct repair value
- Error detection and repair generation are decoupled: any upstream detector flags erroneous cells, then HoloClean's inference step decides the replacement value holistically across the whole dataset rather than cell-by-cell
- Scaling optimizations (factor graph pruning, domain pruning per cell) let inference run over instances with millions of tuples

**Main findings**
- Ensembles of automatic error detectors alone already reach precision/recall above 0.6/0.8 on multiple real datasets, but repair (choosing the correct replacement value) is the harder problem - single-signal repair methods average F1 below **0.35** and frequently produce zero correct repairs on some datasets
- HoloClean's holistic combination of constraints + external data + statistics reaches average F1 above **0.8** across the same benchmark datasets
- Scales to datasets with millions of tuples via the described pruning optimizations, addressed as a first-class design goal rather than an afterthought

**Key takeaways**
- Repairing one signal type in isolation (constraints only, or statistics only) systematically underperforms a joint model that reasons over all cells and all signals simultaneously - "holistic" is not a marketing term here, it is the source of the 2x F1 gain
- Decoupling detection from repair means the repair engine's quality is bounded by what evidence detection surfaces, but the repair step itself benefits from batching across the whole dataset rather than committing per-record
- The paper's own numbers argue against per-document, per-signal repair: constraint-only or statistics-only repair leaves most of the achievable F1 on the table

**Relevance**
- Cited as the argument against premature per-doc repair at ingest (H559): HoloClean's core empirical result is that repair quality depends on aggregating signal holistically across many records before committing a fix, which cautions against a KGF repair loop that corrects one chunk's extraction in isolation before the graph has accumulated enough cross-document evidence to repair correctly

**Tags**
- #DataCleaning
- #ProbabilisticInference
- #HolisticRepair

**Source**
- Download: https://arxiv.org/pdf/1702.00820
- Local: [paper] holoclean, 2017.pdf
