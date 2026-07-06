# GenIC: An LLM-Based Framework for Instance Completion in Knowledge Graphs

**Authors**: Amal Gader, Alsayed Algergawy
**Published**: May 2025, arXiv:2505.24036
**Original**: https://arxiv.org/abs/2505.24036
**Local copy**: `[paper] GenIC, 2025-05.pdf`

## Problem

Instance completion: given an entity, predict which property-object pairs are missing and fill them - the whole gap, not just a missing tail for a known relation.

## Mechanism

Two-stage LLM pipeline:

1. **Property prediction** - multi-label classification over the schema: which properties should this entity have, given its description, types, and schema patterns
2. **Object generation** - sequence-to-sequence generation of the tail entity for each predicted missing property

## Results

Outperforms link-prediction baselines on three datasets; code at https://github.com/amal-gader/genic.

## Relevance to KGF

The closest LLM-era system to R04-H23's audit - and the contrast that makes KGF's move distinct: GenIC fills predicted gaps from the LLM's parametric knowledge, which is exactly what a faithful document-grounded graph must not do. KGF keeps stage 1 (predict what is missing - via cohort statistics rather than a trained classifier) and replaces stage 2 with repair-from-source: the gap becomes a focused re-extraction question against the documents that mention the entity. Fill only from evidence; otherwise record the gap as negative knowledge.
