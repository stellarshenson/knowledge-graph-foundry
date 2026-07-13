**TABi: Type-Aware Bi-Encoders for Open-Domain Entity Retrieval (2022)**

Text-only entity retrievers learn popularity bias - they resolve an ambiguous mention like "George Washington" to whichever entity dominates the training distribution (the president, not the baseball player) and fail on rare "tail" entities that share a name with something popular. TABi jointly trains a bi-encoder on unstructured text and knowledge-graph types via a type-enforced contrastive loss, pulling entities and queries of similar type together in embedding space without requiring mention-boundary annotation. On the AmbER ambiguous-entity benchmark, TABi improves average tail accuracy@1 by **34.9 points** over text-only baselines and **6.8 points** over prior type-aware baselines, while remaining robust down to just **5% type coverage** of the training data.

**Key mechanism**
- A single tied bi-encoder f ≡ g embeds both queries and entity descriptions into the same space; retrieval is nearest-neighbor lookup
- Loss is a weighted sum L = αL_type + (1-α)L_ent (α = 0.1 in experiments), both terms are supervised contrastive losses (Khosla et al.) computed within a training batch
- L_type forms positive pairs from queries sharing the same KG type and negative pairs from queries of a different type - this clusters entities by coarse type (politician, athlete, musician, ...) in embedding space
- L_ent forms positive pairs from query/entity-description pairs sharing the same gold entity, clustering fine-grained identity as in a standard dense retriever
- Hard-negative mining adds the top nearest incorrect entities to each batch, with the positive/negative ratio balanced per entity so rare entities are not swamped by hard negatives
- Because the loss only needs entity-level type labels (not mention boundaries), it applies directly to unstructured open-domain text, unlike prior type-aware methods that require pre-segmented mentions

**Main findings**
- AmbER (mention detection required, KILT-trained models): TABi improves average tail accuracy@1 by **34.9 points** over text-only baselines (best text-only baseline 36.9% -> TABi 72.1%) and **6.8 points** over the strongest type-aware baseline
- AmbER (GOLD, mention boundaries given, Wikipedia-disambiguation-trained): TABi still beats baselines by **4.4 points** average tail accuracy@1
- Ablation removing the type-enforced loss (α = 0, i.e., text-only L_ent): tail accuracy drops by **5.8 points** and head accuracy by **3.0 points**, isolating the type loss's specific contribution
- Overall performance is not sacrificed for the rare-entity gain: TABi outperforms all retrievers on AmbER head accuracy@1, and on the KILT benchmark it beats GENRE (best prior multi-task retriever) by 1 point overall while setting SOTA on three of KILT's constituent tasks
- Robust to sparse type annotation: improves rare-entity retrieval over baselines even with only 5% of the training set carrying a type label, showing the contrastive signal generalizes from a small typed subset

**Key takeaways**
- Type information is most valuable as a training-time contrastive signal, not as an inference-time filter - the embedding space itself learns to separate by type, so no mention-boundary detection or type lookup is needed at query time
- A held-out low-coverage regime (5% typed) still captures most of the benefit, meaning a KG with incomplete or noisy type annotations is still a usable training signal, not a blocker
- Combining a coarse type-contrastive term with a fine-grained identity-contrastive term in one joint loss is a general recipe: type clustering fixes systematic popularity bias while entity clustering preserves precise identity resolution

**Relevance**
- Directly actionable for R50's typed retrieval question: KGF's typed entity graph could supply the type labels for a TABi-style contrastive fine-tune of the embedding model used in entity/candidate retrieval, targeting exactly the tail-entity failure mode KGF has documented in cross-type duplicate resolution
- The joint L_type + L_ent loss structure is a candidate blueprint for retrofitting KGF's existing embedding-based resolver with type awareness without requiring mention-span annotation on ingest text

**Tags**
- #EntityRetrieval
- #BiEncoder
- #TypeAwareness
- #ContrastiveLearning

**Source**
- Download: https://arxiv.org/abs/2204.08173
- Local: [paper] TABi type-aware bi-encoders, 2022.pdf
