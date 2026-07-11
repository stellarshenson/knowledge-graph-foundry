# R41 literature brief - speculative in-memory graph construction to span the graph

Prepared 2026-07-11 for the R41 hypothesis fanout. User directive (verbatim intent): "research about speculative in-memory graph construction to span the graph", course-corrected mid-round to its PRIMARY sense: ingestion-time, about ENTITIES - while extracting chunk N, speculatively construct an in-memory graph fragment that spans the committed graph and the in-flight document, and inject it as expanded context so the LLM pins entities to existing graph identities instead of re-inventing them. Sources: local paper library plus 10 papers downloaded for this brief (ReLiK, GENRE, KB-Injection, iText2KG, NELL, Knowledge Vault, Speculative Decoding, Speculative RAG, DrKIT, UKGE), all archived with digests in `references/papers/`.

## 1. Pinned definition and design space

**Pinned definition** - speculative in-memory graph construction is the practice of building provisional graph structure (candidate entities, hypothesized edges, context fragments) cheaply and revocably in memory, whose purpose is to SPAN gaps - between the committed graph and an in-flight document at ingest, or between disconnected components at read time - before any expensive verification, with a hard contract that speculation never enters the trusted tier unverified. The primary KGF instance: a per-chunk spanning fragment of committed entities (names, aliases, types, distinguishing facts) injected into the extraction prompt as a HYPOTHESIS about what the chunk concerns, so extraction pins mentions to existing identities - cheap to build, revocable, and measured on pin precision, not just naming consistency.

The design space, five senses with published precedent:

- **S-A (PRIMARY) - ingestion-time spanning context for entity pinning** - retrieve candidate committed entities the chunk plausibly touches, inject into the extraction prompt, extractor aligns mentions to injected identities or declares them new. Precedent: ReLiK (candidates + text in one reader pass, SOTA EL/RE at 40x speed), KB-Injection (+5% joint IE F1 from EL-candidate injection), GENRE (constrained decoding onto canonical names - the hard form), iText2KG (matched-entity context, with a measured -10% precision anchoring cost), LINK-KG (alias caches across chunks - already in the library)
- **S-B - speculative edge/node hypothesis tier at ingest** - link-prediction or heuristic candidates held provisionally pending verification. Precedent: Knowledge Vault (1.6B scored candidates, 271M promoted at >= 0.9 calibrated confidence; PRA + embedding priors AUC 0.884/0.882), UKGE (confidence-valued edges as first-class), HippoRAG synonym edges (tau = 0.8, never individually verified - accepted wholesale, the degenerate case)
- **S-C - query-time transient subgraph construction** - bridges computed in memory per query, used, discarded; zero trust machinery needed because nothing commits. Precedent: DrKIT (virtual KB, +9 pts MetaQA 3-hop, 10-100x QPS; the whole graph is speculative)
- **S-D - speculative execution economics** - draft cheap, verify lazily, acceptance rate governs worth. Precedent: Speculative Decoding (2-3x speedup, provably identical output distribution - the correctness contract transfers as doctrine), Speculative RAG (draft-verify wins accuracy +12.97% AND latency -50.83% in a knowledge task; diverse parallel drafts are themselves an accuracy lever)
- **S-E - two-tier committed/speculative stores with promotion rules** - candidate facts vs beliefs. Precedent: NELL (promotion at posterior > 0.9 or multi-source agreement, mutual-exclusion vetoes, 242k beliefs / 74% precision / 67 days; its never-demote flaw is the canonical negative lesson), Knowledge Vault (calibrated threshold as promotion policy)

## 2. Why KGF needs the primary sense - the measured hole

- **H107 CONFIRMED** - 71% of the duplicate problem is extraction surface-form variance within single documents, UPSTREAM of the resolver; "no resolver improvement can prevent what extraction keeps re-creating"
- **H119 REFUTED decisively** - canonicalization PROMPT WORDING did not cure variance (it worsened it, -9.7%); "determinism is NOT a prompt property... in-prompt naming rules never targeted the real mechanism". Critically, H119 never fed the GRAPH back into extraction as context - graph-context-augmented extraction is the untested lever
- **The prompt injects types, never instances** - `extraction/prompts.py:1` "current ontology state injected" = the 26 cured TYPE definitions and relationship-type names only; no committed entity, alias, or distinguishing fact ever reaches the extractor. The extractor re-derives identity from raw text every chunk, and the Bayesian resolver + demotion court repair downstream what pinning would prevent upstream
- **The repair bill is measured** - H211: 4 of the 8 unranked-residue golds are extraction-side misattribution (codes/values on the wrong entity); the model_code SAME_AS surface (73/127 edges, mask↔battery over shared 'P10') is exactly a disambiguation the spanning fragment would resolve by SHOWING both candidates and their distinguishing facts; v2-vs-v1 census: 2201 vs 2937 entities at fewer merges re-confirmed extraction as the primary identity lever
- **Existing context machinery is one-directional** - `extraction.header_carryover` (R15-H153) re-prints table headers on severed continuation chunks: document → chunk context exists; graph → chunk context does not. LINK-KG's per-type alias caches are the published cross-chunk analogue
- **Best current variance cure is brute force** - R22 3-of-5 extraction voting: 35% churn reduction at 100% stable retention, a 5x cost multiplier. Pinning attacks the same variance at ~1x extraction cost plus context tokens

## 3. What KGF already has that is proto-speculative

- **SIMILAR_TO soft links** - three creators (kNN densify, defer-zone posterior links, demotion court), ZERO consumers; H288: a soft link carries a merge's entire render-recall value (+0.0 delta vs hard merge); H302: 64.7% of sibling-fragment attachment misses close over a posterior-weighted soft edge; but R34-H370 REFUTED render traversal - flat, and the parent-tier bridge edges the failures needed DO NOT EXIST (creator gap: embedding-kNN misses token-poor parent fragments). The speculative-edge tier exists structurally and fails at candidate GENERATION, not consumption
- **Demotion court, demote-don't-delete** - judged-false SAME_AS edges demoted to SIMILAR_TO, never deleted (98.0% false-merge detection): revocation with zero information loss - the promotion/demotion half of a two-tier contract, already shipped
- **H365 spec-hoist marks** - derived bridge edges + hoisted props with `spec_hoisted` markers: committed derived structure, one-shot reversible; H376 measured its provenance thin spot (hoisted `prop_*` fields 0/2 reconstructable at field level) - the cautionary tale for speculative objects without full justification records
- **Defer-band ledger** - the resolver's undecided pairs parked invisibly; a provisional store with no read path and no expiry - a speculative tier missing its promotion rules
- **HippoRAG synonym layer (the peer's answer)** - tau = 0.8 cosine edges at 7-9x relation-edge mass, never individually verified: wholesale-accepted speculation that WORKS for them (+2.4 avg R@5) because they have no entity resolution; R39-H393 already registers the claim that KGF's merges make that layer redundant. Fence respected - R41 does not re-propose synonym traversal
- **Rejection quarantine doctrine (R39-H395)** - rejections persist as provenance-carrying ledger objects, never silent: the trust template every R41 speculative object inherits

## 4. Trustworthiness contract - how speculation coexists with the certificate doctrine

The committed graph is the product; speculation is scaffolding. Rules synthesized from NELL's flaw, Knowledge Vault's calibration, speculative decoding's guarantee, and KGF's own quarantine doctrine:

- **Tier separation** - speculative objects live in a marked tier (label or property, `(:KGFSpeculative)` class or `spec_*` prefix per H365 precedent); every committed-tier read path excludes them by default; render/retrieval touches them only through explicit, flagged channels
- **Provenance mandatory** - every speculative object carries creator, basis (the evidence that generated it), score, and timestamp - the H376 justification-record finding says KGF's provenance is thick enough to support this today except for hoisted props (the one thin field, fix inherited by R41 objects)
- **Prompt-time speculation leaves no residue unless adopted** - the injected spanning fragment is transient (in-memory, per-chunk); the ONLY durable trace is the pin record when the extractor adopts a candidate (mention → graph id, with the injected evidence hash). A wrong injection that the model ignores costs tokens only - the speculative-decoding contract: rejected drafts must leave the committed distribution untouched
- **Pins are hypotheses, not commits** - a pin is a high-prior input to the resolver, not a bypass of it; the resolver's posterior still adjudicates, so a wrong pin is catchable downstream (and the pin record makes it auditable - unlike today's silent re-invention)
- **Promotion rules** (S-B/S-E objects) - NELL/KV pattern: promote on calibrated posterior above threshold OR multi-source agreement, subject to ontology vetoes (mutual exclusion, type constraints); NEVER silent promotion; R38 calibration certificates are the calibration instrument
- **Demotion/expiry mandatory** - NELL's never-demote is the documented failure; KGF's demotion court is the existing answer; speculative objects additionally carry expiry (unpromoted after N ingest cycles or M retrieval outcomes → archived to the gap ledger, not deleted) - R36's derived-object invalidation findings apply to the speculative tier from day one
- **Composition with the coverage machinery (R39-H389/H394)** - a pinned entity is an AUDITABLE object: the coverage certificate can verify the pin against the source span (mention text vs graph identity's distinguishing facts), and pin records give H389's miss-list a new detection class (fact extracted but attached to a wrong pin). An invented duplicate is a coverage miss waiting to happen - its facts land on an entity retrieval will not find (H236 fragment class). Pinning shrinks H394's repair loop: targeted re-extraction can carry the pin context, and certified misses can name the entity they SHOULD have attached to

## 5. Proven-novel open slots

Verified against the local library (~90 papers) and this brief's 10 downloads:

- **S-P1 - pin-precision-measured graph-context extraction.** iText2KG measures context-injection precision cost (-10%) but injects the GLOBAL entity list undifferentiated and never measures pin precision (mention→identity correctness) or downstream identity fragmentation; ReLiK/KB-Injection/GENRE operate against static curated KBs (Wikipedia), never against a growing self-extracted graph where the candidate inventory is itself noisy. Nobody measures the closed loop: graph → context → extraction → graph identity quality. Open
- **S-P2 - speculation-aware candidate retrieval policy.** What fragment to inject is unstudied: ReLiK retrieves top-k by dense similarity; LINK-KG carries per-type alias caches; iText2KG injects everything global. No published comparison of kNN vs typed-neighborhood vs working-set policies, and no policy conditioned on the false-pin risk (injecting sibling model codes is the dangerous case - 'P10' mask vs 'P10' battery). Open
- **S-P3 - pin ledger as identity provenance.** No system records extraction-time pinning decisions as auditable objects; entity provenance in the literature is source-document-level (KGF already has that), never decision-level (why this mention joined this entity). The pin ledger is the H101-adjudication queue for identity, analogous to H395's quarantine for admission. Open
- **S-P4 - targeted bridge-candidate generation for the creator gap.** H370's post-mortem: the speculative edges that were needed (parent-tier fragments) are invisible to embedding-kNN; link-prediction literature (KV priors, UKGE) scores CANDIDATES it is given from dense signals. Structural candidate generators (shared stem + missing parent, PART_OF orphan patterns) feeding a scored speculative tier are unpublished. Open, but SECONDARY per the course correction
- Anti-slot (checked, closed): draft-verify KG extraction exists in spirit (GraphJudge verifies drafts; R39-H395 owns admission verification); two-tier KBs exist (NELL/KV); transient query-time graphs exist (DrKIT). R41's novelty is confined to S-P1-S-P4

## 6. Hypothesis candidates

Numbering: placeholders HX+1..HX+7, assigned after R40 registration to keep numbering monotonic. Naive baseline for the ingestion-time candidates: the production extractor (types-only prompt, no instance context), measured on the H119 5x re-extraction harness (churn), the H107 duplicate-pair census, and a new pin-precision instrument; comparison lever: R22 3-of-5 voting (35% churn reduction at 5x cost).

### HX+1 (conformist) - spanning-context injection: the graph pins its own entities

- **Mechanism** - before extracting chunk N, retrieve candidate committed entities (kNN on chunk embedding + lexical/model-code match), build an in-memory spanning fragment (canonical name, type, aliases, 2-3 distinguishing facts each, capped ~10 candidates), inject into the extraction prompt with instructions: reuse the canonical name when the mention IS that entity, declare new otherwise; emit a pin record per adopted candidate
- **Grounding** - ReLiK (candidates-in-input = SOTA EL/RE), KB-Injection (+5% F1 from candidate injection with attention that can DISCOUNT wrong candidates), LINK-KG (alias continuity across chunks raises graph completeness), H107 71% / H119 refutation (wording failed; context untested), prompts.py types-only gap
- **Prediction** - H107-class duplicate-pair creation drops >= 30% on a re-ingest A/B (approaching R22 voting's 35% at ~1/5 the LLM cost); run-to-run entity-set churn drops where H119's wording could not move it; pin precision >= 95% on a hand-adjudicated sample
- **Bar sketch** - A/B re-ingest of the benchmark corpus: duplicate census delta >= 30%, pin precision >= 95%, zero regression on extraction fact coverage (H389 instrument if landed, else proposition counts), context growth <= 40% of extraction prompt; REFUTED if pin precision < 90% (wrong pins are worse than duplicates - they MERGE distinct entities silently at extraction, upstream of every safety net)
- **Composes with** - resolver (pins as high-prior inputs, not bypasses), pin ledger (HX+4), H389 coverage audit

### HX+2 (conformist) - candidate retrieval policy: what to inject

- **Mechanism** - sweep the spanning-fragment construction policy: (a) kNN entities only; (b) typed neighborhood (candidates + 1-hop PART_OF/IS_MODEL_OF parents - the tier H370 showed kNN misses); (c) recent-document working set (LINK-KG-style alias cache from chunks N-k..N-1 + committed matches); (d) name-only vs name+distinguishing-facts rendering. Fixed extractor, fixed corpus; measure pin precision/recall, duplicate delta, tokens per arm
- **Grounding** - S-P2 open slot; iText2KG global-vs-local (-10% precision when the inventory is undifferentiated - policy MATTERS); H370 creator gap (parent-tier context is the known blind spot); header_carryover as the existing working-set precedent
- **Prediction** - (c)+(d) wins: working-set continuity catches the "the device/unit" continuation class (H21 forensic), distinguishing facts prevent the sibling-code false pins; name-only arms show measurably worse pin precision on model-code collisions
- **Bar sketch** - per-arm pin precision on a seeded hard set (>= 20 sibling/model-code collision cases from the H107 inventory); the winning arm beats kNN-only by >= 5 pts pin precision at <= 1.5x its token cost; REFUTED (policy irrelevant) if all arms tie within 2 pts - then HX+1's simplest form ships
- **Composes with** - HX+1 (supplies its production policy), extraction concurrency memory (c64/t3600 - injected tokens scale per-chunk latency)

### HX+3 (follower) - pin economics: context tokens vs repair savings

- **Mechanism** - full cost ledger for HX+1's winning arm: injected tokens + retrieval cost per chunk vs measured downstream savings (resolver candidate-pair volume, defer-band size, demotion-court docket, duplicate-repair passes); frame as speculative-execution acceptance rate - fraction of injected candidates adopted (alpha) prices the speculation
- **Grounding** - Speculative Decoding (alpha governs worth; speculation pays when draft << verify), R29 measured the court at ~65k tokens/graph and the resolver's workload scales with duplicate volume; R22 voting = the 5x-cost alternative
- **Prediction** - alpha >= 0.3 (chunks in a coherent corpus mostly touch known entities after doc 3-4, mirroring cure-at-doc-4); net cost NEGATIVE (savings exceed injection) once the corpus passes ~10 docs, because resolver work scales superlinearly with duplicate mass
- **Bar sketch** - end-to-end ingest cost A/B at equal quality: injection arm <= baseline arm total tokens once repair is included; report alpha per document position (the speculation should get cheaper as the graph grows - the spanning fragment hit rate rises); REFUTED if alpha < 0.1 (chunks rarely touch the committed graph - the corpus is too heterogeneous for pinning to pay)
- **Composes with** - HX+1/HX+2, throughput settings, idle-card economics (H363 pattern)

### HX+4 (follower) - the pin ledger: identity decisions become auditable objects

- **Mechanism** - every adopted pin persists as a ledger record: mention text, source span, pinned graph id, injected-evidence hash, extractor confidence; every DECLINED candidate list too (chunk saw candidates, pinned none - the new-entity declaration). The ledger is the identity analogue of H395's rejection quarantine: no silent identity decision anywhere in ingest
- **Grounding** - S-P3 open slot; R39-H395 quarantine doctrine (provisional objects with provenance, never silent); H376 (justification records reconstructable today for entities/edges - pins extend the same discipline to decisions); the H101 adjudication queue precedent
- **Prediction** - the ledger turns wrong pins into a detectable class: a post-ingest audit (resolver posterior vs pin confidence disagreement) surfaces >= 80% of seeded wrong pins with < 10% review burden; coverage composition holds - H389's audit can attribute misses to "fact extracted, wrong pin" as a distinct class
- **Bar sketch** - seeded wrong-pin recovery >= 80% at <= 10% ledger-review fraction; ledger cost < 5% ingest overhead; zero read-path leakage (committed queries never touch pin records); GATED on HX+1 confirming pins exist to ledger
- **Composes with** - H389/H394 (pinned entities are auditable; the certificate cites pin records), demotion court (wrong-pin repair reuses its machinery)

### HX+5 (contrarian) - injected context anchors the extractor to WRONG entities and costs more than repair

- **Mechanism** - claim: the spanning fragment is a leading question. The LLM pins mentions to injected candidates the chunk does not actually concern (anchoring), especially on sibling model codes and near-alias products; wrong pins merge distinct entities AT EXTRACTION - upstream of the resolver's evidence, harder to detect than duplicates (a duplicate is visible as two nodes; a wrong pin is one node silently absorbing another's facts). Total cost (wrong-pin damage + audit + tokens) exceeds the downstream Bayesian-repair bill it replaces
- **Grounding** - iText2KG measured the anchoring direction: global-entity context costs ~10% triple precision via implied-relation extraction (0.94 → 0.83); the model_code false-merge surface ('P10' mask↔battery) shows KGF's corpus has exactly the decoy structure that maximizes anchoring risk; H211's misattribution class shows the extractor already over-attaches under NO context - context could amplify it
- **Prediction** - decoy-injection arm (spanning fragments seeded with plausible-but-wrong siblings): pin precision on decoys < 90%; fact-level damage: facts of the true entity land on the decoy at a rate exceeding the baseline duplicate-fragmentation rate; the economics ledger (HX+3) goes NEGATIVE when wrong-pin repair is priced
- **Bar sketch** - CONTRARIAN CONFIRMED if decoy pin precision < 90% OR HX+3's net cost is positive with wrong-pin repair included → injection ships only in a restricted form (exact-name/alias matches, no similarity candidates) or not at all; REFUTED if decoy precision >= 95% AND net cost negative - the model discounts wrong candidates as KB-Injection's attention did
- **Composes with** - HX+1 (same harness, adversarial arm), HX+4 (the ledger is what makes wrong pins measurable at all)

### HX+6 (follower, secondary sense) - two-tier speculative bridge ledger with structural candidate generation

- **Mechanism** - S-B/S-E composed for the H370 creator gap: a structural candidate generator (shared name stem + missing parent, PART_OF orphans, childless series fragments - the H365 class) proposes bridge-edge hypotheses; each is scored (resolver posterior features + KV-style graph prior), held in the speculative tier with provenance, and promoted NELL/KV-style (calibrated score above threshold or corroboration by a later document) or expired to the gap ledger
- **Grounding** - H370 post-mortem (needed bridges structurally token-poor, invisible to kNN - candidate generation is the failure point); H375 corollary (token signatures VERIFY repairs post-hoc but cannot discover them - discovery needs structural rules); NELL promotion + veto rules; Knowledge Vault calibrated tiers; UKGE scoring
- **Prediction** - the structural generator proposes the HC230/'Sleep Style 200 Series' fragment pair (rank <= 20 of its candidate list) that kNN ranked 58,062; on the rebuilt graph, >= 50% of H365-class parent-tier fragments receive a correct speculative bridge before any repair runs
- **Bar sketch** - candidate list contains the known fragment pairs pre-repair (the H375 honesty protocol: measured on the PRE-repair graph); precision of promoted bridges >= 90% on hand adjudication; zero committed-tier contamination (promotion only through the registered rule); REFUTED if the structural rules generalize to < 3 candidate classes (a hand-coded fix dressed as a mechanism)
- **Composes with** - defer-band ledger (same tier), demotion court (demotion path), R36 expiry discipline, H365 (whose one-shot repair becomes the promoted output of a standing mechanism)

### HX+7 (heretical) - nothing is committed: the graph is a speculative store that earns trust per-object

- **Mechanism** - invert the tiers. ALL extraction lands in the speculative tier; "committed" is not a write destination but a PREDICATE earned per object: provenance complete + coverage-audit support (H389) + calibration certificate (R38) + N retrieval outcomes without contradiction. Ingestion returns immediately with provisional structure (retrieval can use it, flagged); trust anneals in the background as audits run. The trustworthy graph stops being a construction promise and becomes a queryable property: `WHERE trusted = true` is the certificate
- **Grounding** - Knowledge Vault IS this at web scale (everything is a scored hypothesis; 0.9 defines the product); KGF's own drift: R29 both arms already emit ZERO hard SAME_AS (identity is entirely soft links + court demotions - the identity layer has ALREADY inverted de facto); the FSM's dead RECURING state and R36's invalidation gaps show committed-as-default rots silently anyway
- **Prediction** - on the benchmark corpus, the trusted-subgraph fraction converges to >= 85% of objects within one audit cycle; retrieval restricted to trusted-only loses < 2 recall points vs the full graph (most of what retrieval needs earns trust fast); the untrusted residue is ENRICHED for known failure classes (P08 parse loss, fragment carriers) - the tier boundary becomes the failure detector
- **Bar sketch** - prototype as labels + audit backfill on the live graph (no engine rewrite): trusted-fraction and trusted-only recall measured; CONFIRMED if the untrusted residue's failure-class enrichment >= 3x base rate (the inversion pays as an instrument even before it pays as architecture); REFUTED if trusted-only recall drops >= 5 pts (trust-gating starves retrieval and the committed-by-default doctrine stands)
- **Composes with** - R38 certificates (the trust predicate's vocabulary), H389/H394 (audits as trust sources), R36 (invalidation = trust revocation), gap ledger (the untrusted residue's home)

## 7. Registration table sketch

| Placeholder | Persona | Lever | Headline prediction | Bar |
|---|---|---|---|---|
| HX+1 | conformist | spanning-context injection at extraction | duplicates -30%, pin precision >= 95% | A/B census + precision + <= 40% context growth |
| HX+2 | conformist | candidate retrieval policy sweep | working-set + distinguishing-facts wins | >= 5 pts pin precision over kNN at <= 1.5x tokens |
| HX+3 | follower | speculation economics (alpha ledger) | net ingest cost negative past ~10 docs | full-cost A/B incl. repair; alpha reported |
| HX+4 | follower | pin ledger (auditable identity decisions) | >= 80% seeded wrong-pin recovery | <= 10% review burden, < 5% overhead |
| HX+5 | contrarian | anchoring: wrong pins cost more than repair | decoy pin precision < 90%, negative economics | decoy arm + priced repair; >= 95% refutes |
| HX+6 | follower | structural bridge candidates → two-tier ledger | HC230 pair in top-20 candidates pre-repair | >= 90% promoted-bridge precision, zero contamination |
| HX+7 | heretical | trust as earned per-object predicate | untrusted residue 3x-enriched for failures | trusted-only recall within 5 pts |

Sequencing: HX+1 first (the instrument and the lever), HX+5 runs as its adversarial arm on the same harness, HX+2 refines the winner, HX+3/HX+4 ride it; HX+6 independent (secondary sense); HX+7 is a labels-only prototype, cheap and parallel. Fences: R39 owns extraction-coverage instruments (H389-H395 - HX+1/HX+4 CONSUME them, never re-propose); R22 owns voting; R34 owns retrieval-side levers incl. SIMILAR_TO render access (refuted, stays refuted); R35 owns question objects; R36 owns invalidation machinery (HX+7's revocation path cites, not rebuilds).

## 8. Source register

Downloaded for this brief (all PDF-verified, digests beside them in `references/papers/`):

1. `[paper] ReLiK, 2024-08.pdf` - retriever-reader EL/RE, candidates in one reader pass, 40x inference speed, SOTA in/out-of-domain (arXiv 2408.00103)
2. `[paper] GENRE Autoregressive Entity Retrieval, 2020-10.pdf` - trie-constrained canonical-name generation, ~2GB footprint, 83.7 avg Micro-F1 ED (arXiv 2010.00904, ICLR 2021)
3. `[paper] KB-Injection Joint IE, 2021-07.pdf` - EL-candidate embeddings into joint NER/coref/RE, up to +5% F1, attention discounts wrong candidates (arXiv 2107.02286)
4. `[paper] iText2KG, 2024-09.pdf` - incremental construction; global-entity context costs ~10% triple precision vs local (0.94→0.83, 0.90→0.81) (arXiv 2409.03284)
5. `[paper] NELL Never-Ending Language Learning, 2010-07.pdf` - candidate/belief tiers, promotion posterior > 0.9 or multi-source, never-demote flaw, 242k beliefs / 74% / 67 days (AAAI 2010)
6. `[paper] Knowledge Vault, 2014-08.pdf` - 1.6B scored candidates, 271M at >= 0.9; PRA prior AUC 0.884, MLP 0.882; calibrated promotion (KDD 2014)
7. `[paper] Speculative Decoding, 2022-11.pdf` - draft-verify, 2-3x speedup, identical-distribution guarantee, alpha economics (arXiv 2211.17192, ICML 2023)
8. `[paper] Speculative RAG, 2024-07.pdf` - small drafter + large verifier, +12.97% accuracy / -50.83% latency (arXiv 2407.08223)
9. `[paper] DrKIT Virtual Knowledge Base, 2020-02.pdf` - query-time virtual KB, +9 pts MetaQA 3-hop, 10-100x QPS (arXiv 2002.10640, ICLR 2020)
10. `[paper] UKGE Uncertain KG Embedding, 2018-11.pdf` - confidence-valued edges, PSL-coupled unseen-fact scoring (arXiv 1811.10667, AAAI 2019)

Load-bearing pre-existing library: `[paper] link-kg coref kg construction, 2025.pdf` (per-type alias caches across chunks), `[paper digest] HippoRAG.md` / `HippoRAG 2.md` (tau = 0.8 synonym layer, 7-9x edge mass, wholesale-accepted speculation), GraphJudge/ODKE+ (R39's admission verifiers), Mem0/A-MEM (working-memory patterns). Internal: `docs/experiments/kgf-redesign-experiments.md` (H107, H119, H153, H211, H288, H302, H365, H370, H375, H376, R29, R39 registrations), `src/knowledge_graph_foundry/extraction/prompts.py`, `ingest/chunking.py:27-82`, `reports/r39-graph-construction-literature-brief-20260711.md`.
