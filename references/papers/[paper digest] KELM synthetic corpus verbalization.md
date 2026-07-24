**Knowledge Graph Based Synthetic Corpus Generation for Knowledge-Enhanced LM Pre-training (KELM / TEKGEN), Agarwal, Ge, Shakeri, Al-Rfou (UPenn / Google Research), NAACL 2021 (arXiv 2010.12688)**

The reference method for turning KG triples into natural-language text at scale - the exact operation entity strengthening needs when self-extracted nodes have no descriptions. A verbalization pipeline (TEKGEN) converts (subject, relation, object) groups into fluent sentences over the entire English Wikidata KG, producing the KELM corpus (~18M sentences, ~45M triples, ~1,500 relations). Crucially the paper evaluates the verbalized text as RETRIEVAL corpus, not just as pre-training data.

**Key mechanism**
- Align Wikidata triples to Wikipedia sentences via distant supervision, fine-tune T5 to generate a sentence from a group of triples sharing a subject
- Group related triples so one sentence carries an entity's neighbourhood (not one triple in isolation) - coherent multi-fact verbalization
- Output is plain text, so it drops into any existing LM or retrieval index with zero architecture change

**Main findings**
- Augmenting a retrieval LM's corpus with verbalized KG text gives significant gains on open-domain QA and the LAMA knowledge probe
- Verbalization improves factual accuracy and reduces toxicity vs the base LM
- Grouped-triple verbalization beats single-triple: neighbourhood context makes better sentences (the coverage/coherence challenge is real at full-KG scale)

**Relevance to KGF**
- The direct source-of-text answer for family-3 entity strengthening: our self-extracted nodes have NO descriptions - TEKGEN says GENERATE them from the node's triple neighbourhood (neighbourhood verbalization), and that the resulting text measurably improves retrieval
- Confirms text-side enrichment is a retrieval lever, not only a pre-training trick - the verbalized corpus lifted open-domain QA retrieval; this is the TEXT-space analogue of H627's confirmed embedding-space smoothing, and it says the text channel carries real signal
- Grouped-neighbourhood verbalization = exactly the "verbalize the k-hop neighbourhood into a node description" mechanism; its coverage/coherence caveats price the ingest cost
- Ceiling PRICED by R57-H648: if missed carriers do NOT separate from hits on description-length/degree (AUC < 0.55 both), the starved-entity theory is dead and this family deprioritizes regardless of how good verbalization is; H648 must clear AUC >= 0.65 first

**Tags**: #KELM #TEKGEN #Verbalization #NodeText #EntityStrengthening #AmplificationFamily3

**Source**: https://arxiv.org/abs/2010.12688. Local: [paper] KELM synthetic corpus verbalization, 2020.pdf
