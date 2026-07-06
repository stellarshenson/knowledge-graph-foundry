**Materialized View Selection and View-Based Query Planning for Regular Path Queries (2024)**

Given a Regular Path Query workload and a memory budget, this paper picks materialized views (shared subqueries) that minimize total workload cost. The benefit function is proven monotone and submodular, so greedy selection by marginal benefit inherits the (1-1/e) guarantee. On Wikidata with real query logs it delivers a **9.73x speedup** in total query-processing time versus ad-hoc execution.

**Key mechanism**
- Represent the workload as an AND-OR DAG with closure (AODC) encoding subquery relations and detecting view redundancy incrementally
- Benefit f(V) = workload cost reduction, PROVEN monotone and submodular
- Budget enforced by f(V u {v}) = f(V) when over budget
- Greedy selection by marginal benefit (the problem is NP-hard)

**Main findings**
- 9.73x speedup in total query-processing time vs ad-hoc on Wikidata with real query logs
- Budget expressed in result-cardinality

**Key takeaways**
- A workload-aware coverage objective on a graph database is provably submodular
- Greedy inherits the (1-1/e) bound and yields a local-optimum certificate
- The AODC detects redundant views incrementally

**Relevance**
- Our materialization stage as an exact published template - a workload-aware coverage objective on a graph database is provably submodular, so greedy inherits (1-1/e) and yields a local-optimum certificate
- Grounds evidence-path view materialization and the benefit-per-budget knee

**Tags**
- #MaterializedViews #RegularPathQueries #Submodular #GraphDatabase

**Source**
- Download: https://mod.icst.pku.edu.cn/docs/20241209130659496865.pdf
- Local: [paper] rpq materialized view selection, 2024.pdf
