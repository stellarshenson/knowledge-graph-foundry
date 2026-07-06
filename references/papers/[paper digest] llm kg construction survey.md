**LLM-empowered Knowledge Graph Construction: A Survey (2025) | Haonan Bian**

This survey maps the design space of LLM-driven KG construction, organizing it into schema-based paradigms versus schema-free approaches and tracing the competency-question route from CQs to a populated ABox. Its most useful contribution is negative: it finds "no explicit guidance on granularity choices or optimization objectives", marking the granularity question as genuinely open.

**Key mechanism**
- Organizes methods into schema-based paradigms (structure, normalization, consistency) vs schema-free (flexibility, open discovery)
- Traces the competency-question route - LLMs generate CQs, build the TBox, populate the ABox under schema supervision (CQbyCQ, EDC, AutoSchemaKG)
- EDC runs open extraction, semantic definition, and schema normalization via natural-language definitions compared by vector similarity

**Main findings**
- Schema-driven extraction gives "high consistency but limited flexibility"; schema-free "prioritize coverage and discovery over structural regularity"
- LLMs identify classes/properties "with consistency comparable to that of junior human modelers"
- Critically, "no explicit guidance on granularity choices or optimization objectives"

**Key takeaways**
- CQ-to-schema is the accepted use-case-narrowing route
- No published objective decides schema granularity
- Sparse benchmarks - treat the survey as a map, not evidence

**Relevance**
- Locates our system on the map (schema-based, purpose-conditioned, discovery-then-freeze) and confirms CQ-to-schema as the accepted use-case-narrowing route
- Most useful contribution is negative - the absence of any published granularity objective marks "when are 9 types better than 30" as an open problem and a real contribution target
- Treat as map, not evidence (sparse benchmarks)

**Tags**
- #KnowledgeGraphConstruction #LLM #Survey #Schema

**Source**
- Download: https://arxiv.org/pdf/2510.20345
- Local: [paper] llm kg construction survey, 2025.pdf
