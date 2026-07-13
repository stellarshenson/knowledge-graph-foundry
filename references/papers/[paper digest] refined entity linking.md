**ReFinED: An Efficient Zero-shot-capable Approach to End-to-End Entity Linking (2022) | Ayoola, Tyagi, Fisher, Christodoulopoulos, Pierleoni (Amazon Alexa AI)**

ReFinED links mentions to Wikidata's **90 million entities** (15x Wikipedia's 6M) while running **more than 60x faster** than competitive prior systems and beating state-of-the-art entity-linking benchmarks by an average of **3.7 F1**, by doing mention detection, fine-grained typing, and disambiguation for every mention in a document in a single Transformer forward pass.

**Key mechanism**
- Single-pass architecture: one Transformer encodes the whole document once; mention detection (BIO tagging), fine-grained entity typing, and entity disambiguation for all mentions are read off that one set of contextualized embeddings, avoiding the per-mention forward passes that make prior zero-shot models (e.g. Wu et al. 2020) expensive
- Final entity score is a concatenation/combination of three decomposed components: an entity-typing score φ (mention embedding vs. entity's type vector, binary cross-entropy trained), an entity-description score ψ (bi-encoder dot product between mention and entity-description embeddings, enabling zero-shot linking to entities never seen in training), and a global entity prior P̂(e|m) (corpus-frequency/popularity based)
- Candidate generation uses entity priors to shortlist top-30 candidates before scoring, keeping inference cheap even against a 90M-entity KB

**Main findings**
- Ablations isolate each component's contribution: removing entity priors costs 5.0 F1 on AQUAINT but actually gains 1.2 F1 on ACE2004 (dataset-dependent, since priors overfit to popular entities); removing entity types or descriptions each costs several points too - all three components are complementary, none dominates
- Generalizes from Wikipedia-scale (6M entities) to Wikidata-scale (90M) without a Wikipedia-derived title/category/first-sentence crutch, unlike most prior EL work
- Deployed in production; combination of speed, accuracy, and KB scale makes it viable for web-scale extraction pipelines

**Key takeaways**
- This is the concrete architecture behind the H564 baseline: type-score x description-embedding-score x prior is a feature-decomposed carrier scorer, not a single learned blob - each term is independently ablatable and independently interpretable
- The single-forward-pass-per-document design is the efficiency lever that makes 90M-entity linking tractable; worth weighing against KGF's per-chunk extraction cost model
- Zero-shot capability comes specifically from the description bi-encoder term - entities added to the KB after training still get scored via their description embedding, relevant if KGF's entity carrier needs to score against entities it never trained against

**Tags**
- #EntityLinking #ZeroShot #Wikidata #ScoreDecomposition

**Source**
- Download: https://arxiv.org/pdf/2207.04108
- Local: [paper] refined entity linking, 2022.pdf
