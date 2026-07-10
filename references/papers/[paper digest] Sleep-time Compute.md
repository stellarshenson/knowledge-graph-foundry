**Sleep-time Compute: Beyond Inference Scaling at Test-time, Lin, Snell, Wang, Packer, Wooders, Stoica, Gonzalez (Letta / UC Berkeley), 2025-04**

The budget argument for doing derived-object maintenance OFFLINE, between queries. A model "thinks" about a persistent context while idle - anticipating likely questions and pre-computing useful intermediate representations that are written back into the context - so query-time work shrinks. Sleep-time compute reduces the test-time compute needed to reach the same accuracy by **~5x** on Stateful GSM-Symbolic and Stateful AIME; scaling the sleep-time budget lifts accuracy by up to **+13%** (GSM-Symbolic) and **+18%** (AIME); amortizing one sleep-time pass across multiple queries about the same context cuts average cost per query by **2.5x** on Multi-Query GSM-Symbolic.

**Key mechanism**
- Split context from query: at "sleep time" only the context is available; the model generates inferences, restructures the context, and persists the rewritten context
- At test time the (cheaper) query runs against the pre-digested context with a much smaller thinking budget
- Amortization: one offline digestion pass serves all future queries touching that context - the more queries per context, the better the economics
- Works only when queries are PREDICTABLE from context; the paper shows gains shrink as query predictability drops

**Main findings**
- ~5x test-time compute reduction at iso-accuracy on both stateful benchmarks
- Accuracy ceiling raised (+13%/+18%) by scaling offline compute - offline work is not just cheaper, it reaches states test-time scaling alone does not
- 2.5x per-query cost cut when one sleep-time pass is shared by related queries; validated in an agentic SWE case study

**Key takeaways**
- Ingest/idle-time generation (question nodes, hoisted props, summaries) is the compute-shifting pattern with measured economics - the KGF retrieval-first principle, benchmarked
- Query predictability is the eligibility criterion for pre-computation: generate derived objects where the query distribution is guessable, stay lazy where it is not
- Idle-cycle maintenance loops (regenerate stale derived objects while no queries are in flight) have a published cost model to cite

**Tags**: #SleepTimeCompute #OfflineCompute #Amortization #AgentMemory #Letta

**Source**: https://arxiv.org/abs/2504.13171. Local: [paper] Sleep-time Compute, 2025-04.pdf
