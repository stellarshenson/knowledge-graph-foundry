# Instruction Tuning LLMs on Graphs

**Title**: Can Large Language Models Analyze Graphs like Professionals? / Instruction Tuning LLMs on Graph tasks (see arXiv for exact title)
**Authors**: See arXiv listing (source of truth below)
**Source (re-download)**: https://arxiv.org/abs/2408.05457
**Publication date**: 2024-08 (first arXiv version)

## Core mechanism + measured results
- Studies how graph-structured context should be serialized into text for LLMs, and instruction-tunes models on graph tasks
- Compares multiple serialization formats for feeding graph context (edge lists, natural language, JSON, etc.)
- JSON serialization of graph context consistently outperforms the other formats tested
- The gain from JSON serialization is largest for smaller models
- Instruction tuning on graph tasks improves downstream graph-reasoning performance
- Format choice is a measurable, non-trivial lever on accuracy independent of model size

## Relevance to Knowledge Graph Foundry
Guides how KGF should serialize retrieved Neo4j subgraphs into the LLM prompt: prefer JSON encoding of nodes/edges, which matters most if KGF uses smaller/cheaper generation models.
