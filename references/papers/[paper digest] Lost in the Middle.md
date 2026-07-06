# Lost in the Middle

**Title**: Lost in the Middle: How Language Models Use Long Contexts
**Authors**: Nelson F. Liu, Kevin Lin, John Hewitt, Ashwin Paranjape, Michele Bevilacqua, Fabio Petroni, Percy Liang
**Source (re-download)**: https://arxiv.org/abs/2307.03172
**Publication date**: 2023-07 (first arXiv version)

## Core mechanism + measured results
- Evaluates how LLMs use information placed at different positions within a long input context (multi-document QA and key-value retrieval)
- Finds a U-shaped performance curve: models use information best at the very beginning (primacy) and very end (recency) of the context
- Performance degrades sharply when the relevant fact is in the middle - reported >30% degradation vs having it at the edges
- Degradation persists even in models explicitly designed for long contexts
- Longer contexts generally worsen the middle-position penalty
- Practical fix: reorder retrieved passages so the highest-relevance items sit at the head and tail of the prompt

## Relevance to Knowledge Graph Foundry
Dictates how KGF should order PPR/community-summary results in the final prompt: place top-scored subgraph evidence at head and tail, not buried mid-context, to avoid the U-shaped attention loss.
