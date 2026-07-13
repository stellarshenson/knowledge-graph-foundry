**Sufficient Context: A New Lens on Retrieval Augmented Generation Systems**

Google Research introduces a "sufficient context" classifier for RAG failure analysis, showing that large models (Gemini 1.5 Pro, GPT-4o, Claude 3.5) answer correctly when context is sufficient but incorrectly guess rather than abstain when it is not, while a selective-generation method built on this signal improves the fraction of correct answers among responded queries by **2-10%** for Gemini, GPT, and Gemma.

Key mechanism:
- Defines and operationalizes "sufficient context" - an autorater judgment of whether retrieved context contains enough information to answer the query, independent of whether the model actually answers correctly
- Stratifies RAG errors into two buckets: failure to use sufficient context, versus context that is genuinely insufficient
- Proposes a selective-generation method that gates generation on the sufficiency signal to trigger guided abstention

Main findings:
- Larger/stronger models exploit sufficient context well but hallucinate instead of abstaining when context is insufficient
- Smaller/weaker models (Mistral 3, Gemma 2) hallucinate or abstain even when context is sufficient
- Partially-informative context (not fully sufficient) can still raise accuracy versus no context at all
- Sufficiency-gated selective generation improves correct-answer rate among responses by 2-10%

Key takeaways (relevance to KGF): the sufficiency autorater is the direct mechanism for H578 - deciding whether a ledgered span actually supports a proposed repair before committing it, versus abstaining. Separating "context is missing" from "model failed to use context" gives KGF a diagnostic split for its own gap ledger: distinguish retrieval/materialization gaps from generation-time misuse of adequate context.

Tags: sufficient-context, rag-evaluation, abstention, autorater, selective-generation

Source: https://arxiv.org/abs/2411.06037
