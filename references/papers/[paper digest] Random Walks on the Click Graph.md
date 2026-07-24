**Random Walks on the Click Graph, Craswell, Szummer (Microsoft Research Cambridge), SIGIR 2007**

The founding treatment of queries as first-class nodes in a bipartite graph, with retrieval as a random walk across that graph - the classical basis for the query-insertion family. Query-document click pairs form a bipartite graph; a Markov random walk propagates relevance from a query node to document nodes. Its decisive property: it retrieves documents that were NEVER clicked for that query, by reaching them through shared structure - the graph generalizes past the sparse observed edges.

**Key mechanism**
- Bipartite click graph: query nodes on one side, document nodes on the other, edges = observed clicks (noisy, sparse soft-relevance)
- "Backward" random walk from the query node produces a probabilistic document ranking; self-transition probability controls how far propagation spreads
- Best configuration: LONG backward walk with HIGH self-transition probability (stay-and-spread, not run-away)
- Generalization is the point: a query reaches relevant-but-unclicked documents via co-click structure - new connectivity from an inserted query node

**Main findings**
- Beats forward walk and raw click counts on image-search click logs
- Long walk + high self-transition is the effective regime; short/low-self-transition walks under-propagate
- Handles click sparsity: the walk manufactures ranking signal for query-document pairs with zero direct clicks

**Relevance to KGF**
- The oldest evidence for our family-2 thesis (H371 question-node lineage): inserting a query as a graph node and propagating gives connectivity and reach the raw query embedding does not have - documents "never clicked" = our carriers not in the dense seed pool but reachable once a query node bridges them
- High self-transition = keep mass near the source and spread locally - structurally the SAME lesson as H627 one-step smoothing (local spread beats long-range) and anchor-reset PPR (reset mass concentrated at anchors); it argues a query node should ADD reset/connectivity mass, consistent with "merge the harvest, never the seeds"
- Prices the geometric ceiling H649 measures: a query node wired to (anchors u seeds) is exactly the inserted source; the click-graph result says propagation from it reaches otherwise-unclicked carriers - the count of carriers within 2 hops is the prize
- FREE replay arm: build the query-anchor-seed node, PPR from it, no LLM/GPU

**Tags**: #ClickGraph #QueryAsNode #RandomWalk #QueryInsertion #AmplificationFamily2

**Source**: https://www.microsoft.com/en-us/research/publication/random-walks-on-the-click-graph/. Local: [paper] Random Walks on the Click Graph, 2007.pdf
