**EntGPT: Linking Generative Large Language Models with Knowledge Bases**

EntGPT lifts generative LLM entity linking by up to **36% micro-F1** over naive prompting (EntGPT-P, no fine-tuning, 10 datasets) and by **2.1% average micro-F1** with instruction tuning (EntGPT-I, six QA benchmarks) - showing generative LLMs can match or beat traditional contextual EL models without the complexity of dedicated fine-tuned architectures (2024).

**Key mechanism**: two complementary methods. EntGPT-P is a three-step hard-prompting method that structures the LLM's reasoning toward correct entity linking without any training. EntGPT-I applies instruction tuning to further lift supervised entity linking and downstream QA performance. Both avoid the domain-transfer brittleness of traditional contextual EL models.

**Main findings**: naive prompting badly underperforms on EL; the structured three-step hard-prompt alone recovers up to 36% micro-F1 over naive prompting with zero fine-tuning; instruction tuning adds a further 2.1% and generalizes to six QA benchmarks. Works across both open-source and proprietary LLMs.

**Key takeaways for KGF**: template for a local-vLLM entity attacher - a multi-step generative disambiguation prompt (candidate reasoning before final link decision) lifts linking accuracy substantially without fine-tuning, which matters for a locally-hosted model where fine-tuning is costly. The magnitude of the naive-vs-structured-prompt gap (36%) is a strong prior that prompt structure, not model scale, is the primary lever for KGF's attacher step.

**Tags**: entity-linking, generative-llm, prompting, instruction-tuning, no-fine-tuning

**Source**: https://arxiv.org/abs/2402.06738
