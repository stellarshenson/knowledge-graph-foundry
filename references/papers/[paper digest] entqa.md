**EntQA: Efficient One-pass End-to-end Entity Linking for Questions**

EntQA reframes entity linking as question answering: a **fast dense-retrieval module** proposes candidate entities from the full knowledge base, then a **reading-comprehension module** scrutinizes the document to find each candidate's mention span - inverting the conventional mention-detection-then-disambiguation pipeline. It requires no mention-candidates dictionary and no large-scale weak supervision, and reports strong results on the GERBIL benchmarking platform (ICLR 2022).

**Key mechanism**: retrieve-then-read, one pass. Dense entity retrieval (pretrained bi-encoder) proposes candidates first, without needing mentions identified upfront; a powerful reader (pretrained reading-comprehension model) then locates mention spans for each proposed candidate. This avoids the "find mentions without knowing their entities" bootstrap problem inherent to traditional mention-detection-first pipelines.

**Main findings**: EntQA matches or exceeds prior entity-linking approaches on GERBIL without relying on a mention dictionary, demonstrating that candidate proposal can precede (rather than follow) mention detection when retrieval is strong enough.

**Key takeaways for KGF**: grounds the retrieve-then-verify pattern used as a fallback carrier case - propose candidate entities/identities from the graph first via retrieval, then verify/attach with a reader step, rather than requiring upfront mention resolution. Directly informs designs where entity attachment happens after candidate retrieval rather than before.

**Tags**: entity-linking, retrieve-then-read, dense-retrieval, question-answering, GERBIL

**Source**: https://arxiv.org/abs/2110.02369
