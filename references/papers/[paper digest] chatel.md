**ChatEL: Entity Linking with Chatbots**

ChatEL improves average F1 by **more than 2%** across **10 datasets** by prompting general-purpose LLM chatbots through a three-step framework instead of relying on fine-tuned contextual entity-linking models (2024).

**Key mechanism**: a three-step prompting framework structures the LLM's interaction to return accurate entity-linking decisions - candidate reranking and disambiguation performed purely through strategic prompting of a chatbot, with no task-specific fine-tuning.

**Main findings**: the framework lifts average F1 by 2%+ over baselines across 10 benchmark datasets. Error analysis surfaced a secondary finding: a nontrivial fraction of "errors" were cases where the ground-truth label was itself wrong and ChatEL's prediction was correct, suggesting reported gains understate true performance.

**Key takeaways for KGF**: grounds the LLM-as-linker pattern - using an LLM directly over retrieved context to make entity-linking decisions - which motivates the LLM-as-attacher hypothesis (H568) with an ABSTAIN option when the model is not confident, rather than forcing a link. The ground-truth-error finding is a caution: benchmark labels for entity linking are themselves noisy, relevant when interpreting KGF's own linking accuracy numbers against imperfect gold data.

**Tags**: entity-linking, llm-prompting, chatbot, few-shot, disambiguation

**Source**: https://arxiv.org/abs/2402.14858
