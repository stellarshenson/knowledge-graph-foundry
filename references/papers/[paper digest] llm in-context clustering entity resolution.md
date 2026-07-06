**In-Context Clustering-Based Entity Resolution with LLMs: A Design Space Exploration (2025)**

This work reframes entity resolution from pairwise matching to direct clustering: an LLM is given a set of records and clusters them in a single call, fully zero-shot. The design space exploration finds sets of optimally ~9 records from 4 distinct entities, with a hierarchical variant for larger inputs. Gains reach **up to 150% higher accuracy** and **10% higher F-measure** vs pairwise baselines while cutting API calls **up to 5x**.

**Key mechanism**
- LLM receives a set of records and clusters them in one call (not pairwise)
- Sets are sized optimally ~9 records drawn from 4 distinct entities
- A hierarchical variant handles larger inputs
- Fully zero-shot, no training

**Main findings**
- Up to 150% higher accuracy and 10% higher F-measure vs pairwise baselines
- Cuts API calls up to 5x (5 vs 13 for pairwise on an 8-record example)
- Comparable cost (GPT-4o-mini \$0.15/M tokens)

**Key takeaways**
- Clustering over whole record sets beats greedy independent pairwise decisions
- Training-free and cheap at small record counts
- Over-merging distinct-but-similar records is the main risk

**Relevance**
- Scale-appropriate answer to our cross-type duplicate problem - training-free, could resolve the 47 known duplicates and recompute SAME_AS clusters, competing with the 44%-calibrated Bayesian resolver
- Clustering framing naturally addresses false transitive SAME_AS closures by reasoning over whole record sets rather than independent pairs greedily unioned
- Main risk: over-merging distinct-but-similar products

**Tags**
- #EntityResolution #LLM #Clustering #ZeroShot

**Source**
- Download: https://arxiv.org/pdf/2506.02509
- Local: [paper] llm in-context clustering entity resolution, 2025.pdf
