**UNIFIED-KG-BENCH: A Unified Benchmark for Evaluating Knowledge Graph Construction Methods and Graph Neural Networks (2026)**

Text-derived knowledge graphs are noisy, fragmented, and semantically inconsistent, and when a GNN underperforms on one it is unclear whether the graph or the model is to blame. This paper builds a dual-purpose biomedical benchmark from a single corpus that co-locates two automatically constructed graphs with one expert-curated reference graph, all annotated under one schema, so construction quality and GNN robustness can be measured separately. The headline: relation-aware geometric GNNs stay robust as graphs degrade - RotatE-GCN reaches **Acc 0.594** on the noisiest KGGen graph where RGCN (best on the clean reference at **Acc 0.712 / F1 0.708**) cannot even be run.

**Key mechanism**
- Single corpus: MedMentions (**4,392** PubMed abstracts, CUI-annotated); mentions normalized to UMLS preferred terms so surface forms align across all graphs
- Reference graph G_ref from UMLS-NCI: source-filtered to NCI + English (3.4M → 184k nodes), inverse edges dropped, relations with <50 occurrences pruned, Semantic Network integrated as explicit `is-a` type nodes → **110** relation types, one connected component
- Two text-derived graphs from the same corpus: GT2KG (OpenIE triples + LLM validation, 37k nodes) and KGGen (fully LLM-based extract + resolution via DeepSeek-Chat, 56k nodes)
- Common-node alignment: intersect the three graphs by exact string match, keep semantic types with >100 nodes → **1,032** annotated nodes across **8** semantic types shared by all three
- Task: semantic-supervised node classification, 10/10/80 train/val/test stratified by type, 5 seeds, PLM init (all-MiniLM-L6-v2), PyTorch-Geometric loaders; leaderboard on HF Spaces

**Main findings**
- Clean reference graph: RGCN wins (**Acc 0.712, F1 0.708**); plain GCN/GAT trail (GAT Acc 0.682) - relation-specific transforms pay off when the graph is clean and richly multi-relational (Table 4)
- GT2KG (fragmented, avg degree ~1): all models drop; RotatE-GCN_attn most robust (**Acc 0.565, F1 0.563**) vs GCN 0.392 (Table 4)
- KGGen (5,787 relation types, high noise): RGCN not evaluated - per-relation parameter matrices are computationally prohibitive; RotatE-GCN_attn best (**Acc 0.594, F1 0.580**) (Table 4)
- Structural stats quantify the degradation: G_ref 1 connected component / 184k nodes vs GT2KG 6,987 components and KGGen 2,551 components (Table 3)

**Key takeaways**
- Isolating graph quality from model quality needs a shared-node, shared-schema triple of {clean reference, construction-A, construction-B} - the reference graph is the upper bound that makes construction error legible
- Geometric relation modeling with bidirectional message passing beats relation-specific parameterization under noise and open-schema relation explosion; RGCN's per-relation matrices become a liability, not an asset, as relation count grows
- Node classification alone is a narrow probe; link prediction and KG completion in open-schema settings are named as open work
- Biomedical-only, because reliable expert reference graphs plus consistently annotated corpora are expensive outside that domain - external validity is explicitly limited

**Relevance**
- Directly on-target for the post-RC public-benchmark campaign: a reproducible, extensible construction-quality benchmark with a public leaderboard where KGF could enter as a new text-derived graph via the standardized PyG data-loader interface (`TDGBench().get_data(kg_name=...)`), measured against GT2KG and KGGen under a fixed reader and splits
- The evaluation is node-classification, not multi-hop QA - complements rather than replaces the HotpotQA/MuSiQue-class slices already planned; use it as the construction-quality axis, the QA benches as the retrieval axis
- Domain is biomedical; the KGF benchmark corpus (apnea/CPAP device docs) is adjacent but not identical - schema alignment to UMLS-NCI would be required to submit, a non-trivial cost to record before committing

**Tags**: #KnowledgeGraphConstruction #Benchmark #GNN #Robustness #NodeClassification

**Source**: https://arxiv.org/pdf/2605.05476 - local `[paper] unified benchmark kg construction and gnn, 2026.pdf`; code https://github.com/OthmaneKabal/text_driven_kg_bench
