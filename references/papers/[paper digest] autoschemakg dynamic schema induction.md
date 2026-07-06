**AutoSchemaKG: Autonomous Knowledge Graph Construction through Dynamic Schema Induction from Web-Scale Corpora (2025) | Jiaxin Bai, Wei Fan, Qi Hu, Qing Zong, Chunyang Li, Hong Ting Tsang, Hongyu Luo, Yauwai Yim, Haoyu Huang, Xiao Zhou, Feng Qin, Tianshi Zheng, Xi Peng, Xin Yao, Huiwen Yang, Leijie Wu, Yi Ji, Gong Zhang, Renhai Chen, Yangqiu Song**

KG construction usually needs a predefined schema. AutoSchemaKG runs a fully autonomous LLM pipeline that extracts triples AND induces the schema simultaneously, with no human schema. Applied to **50M+ documents** it builds the ATLAS KGs (**900M+ nodes, 5.9B edges**), and its induced schemas reach **92% semantic alignment** with human-crafted schemas at zero manual intervention.

**Key mechanism**
- Fully autonomous LLM pipeline extracting triples AND inducing schema simultaneously
- Models both entities and events
- Conceptualization organizes instances into semantic categories - no human schema

**Main findings**
- Applied to 50M+ documents, building ATLAS KGs with 900M+ nodes and 5.9B edges
- Induced schemas reach 92% semantic alignment with human-crafted schemas at zero manual intervention
- Graphs outperform SOTA on multi-hop QA and improve LLM factuality

**Key takeaways**
- LLM-induced typing is validated at web scale
- The concept space grows open-endedly with no stopping rule
- 92% alignment is against general human schemas, not task utility

**Relevance**
- Closest published analogue to our discover-then-map pipeline, validating LLM-induced typing at scale
- Instructive difference: it keeps an open-ended ever-growing concept space with NO stopping rule, whereas our Good-Turing curing gate freezes a small task-narrowed inventory - the gate is a genuine differentiator the SOTA does not make
- Honest limitation: 92% alignment is against general human schemas, not task utility - silent on whether a frozen 12-type inventory is task-optimal

**Tags**
- #KnowledgeGraphConstruction #SchemaInduction #LLM #WebScale

**Source**
- Download: https://arxiv.org/pdf/2505.23628
- Local: [paper] autoschemakg dynamic schema induction, 2025.pdf
