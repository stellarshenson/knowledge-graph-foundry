"""R49 carrier attacher and render-staging repair primitives.

Two halves of the repair flow the R49 census produced:

- `attach()` selects the entity a repaired fact is ABOUT, porting the winning
  bakeoff logic (`scripts/experiments/r49_carrier_bakeoff.py`): H568 LLM-as-
  attacher with the source span (CONFIRMED 11/11), H567 artifact abstain gate
  (regex + LLM confirm, 4/4) and H569 anchor name-match, over the H560/H561
  candidate-pool doctrine (candidates = the same-document entity set).
- `stage_fact_on_anchor()` pre-stages a repaired fact onto its reachable
  anchor (R49-H576): the fact sentence is appended to the anchor's description
  and provenance recorded in a `staged_facts` list property.

`llm` is any callable ``(prompt: str) -> str``. A gpt-oss-style reasoning
model must be called with max_tokens headroom and a reasoning_content fallback
(the content field is None when reasoning consumes the budget); that transport
detail lives in the callable, not here.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import re
from typing import Callable, Optional

from knowledge_graph_foundry.events import emit
from knowledge_graph_foundry.models import normalize_name

LLM = Callable[[str], str]

# H567: page-boilerplate prefixes (a list header or a disambiguation line)
ARTIFACT_RE = re.compile(r"^(this is a list|.* may refer to:?$|list of )", re.I)


@dataclass(frozen=True)
class FactSpan:
    """A repaired fact and the source span it was extracted from."""

    fact: str
    span: str = ""
    doc_title: str = ""

    def window(self) -> str:
        """The H568 source window: doc title prepended to the source span."""
        return f"{self.doc_title}. {self.span}".strip()


def is_artifact(fact: str, llm: LLM) -> bool:
    """H567 abstain gate: regex prefilter, then the LLM confirms only the
    regex hits (page boilerplate has no legitimate subject to attach to)."""
    if not ARTIFACT_RE.match(fact.strip()):
        return False
    answer = llm(
        f'Sentence: "{fact.strip()}"\n'
        "Is this sentence page boilerplate (a list header or disambiguation "
        "line) rather than a fact about a specific real-world entity? "
        "Answer yes or no."
    )
    return answer.strip().lower().startswith("y")


def name_match(window: str, doc_entities: list[str]) -> Optional[str]:
    """H569 anchor rule: the candidate whose normalized name occurs in the
    source window; ties resolve to the longest name. None when none anchor."""
    haystack = normalize_name(window)
    anchored = [n for n in doc_entities if normalize_name(n) and normalize_name(n) in haystack]
    if not anchored:
        return None
    return max(anchored, key=len)


def llm_attach(fact_span: FactSpan, doc_entities: list[str], llm: LLM) -> Optional[str]:
    """H568: LLM-as-attacher with the source span. Returns the chosen
    candidate name (mapped back to its canonical form when the answer
    paraphrases it), or None on ABSTAIN / an empty answer."""
    options = ", ".join(doc_entities[:12]) or "(none)"
    answer = llm(
        f'Source text: "{fact_span.window()}"\nExtracted fact: "{fact_span.fact}"\n'
        f"Candidate entities: {options}\n"
        "Which single candidate entity is this fact ABOUT (its subject)? "
        "If the fact is page boilerplate (a list or disambiguation line) with "
        "no legitimate subject, answer exactly ABSTAIN. "
        "Answer with only the entity name or ABSTAIN."
    ).strip()
    if not answer or answer.upper().startswith("ABSTAIN"):
        return None
    pick = answer.strip('"').strip()
    normalized = normalize_name(pick)
    for candidate in doc_entities:
        if normalize_name(candidate) == normalized:
            return candidate
    return pick


def attach(fact_span: FactSpan, doc_entities: list[str], llm: LLM) -> Optional[str]:
    """Select the entity a fact is ABOUT from the same-document candidate pool.

    The attach ladder, cheapest rung first: artifact abstain gate (H567) ->
    name-match fast path (H569) -> LLM attacher with the source span (H568).
    Returns the chosen carrier name, or None when the fact is an artifact or
    the attacher abstains. `doc_entities` is the same-document entity set
    (H560/H561 candidate-pool doctrine) - the caller supplies it.
    """
    if is_artifact(fact_span.fact, llm):
        return None
    anchored = name_match(fact_span.window(), doc_entities)
    if anchored is not None:
        return anchored
    return llm_attach(fact_span, doc_entities, llm)


def stage_fact_on_anchor(
    driver,
    anchor_id: str,
    fact_text: str,
    *,
    source: Optional[str] = None,
    reembed: bool = False,
    embed_fn: Optional[Callable[[str], list[float]]] = None,
    timestamp: Optional[str] = None,
) -> dict:
    """R49-H576: pre-stage a repaired fact onto its reachable anchor.

    Appends the fact sentence to the anchor's description and records
    provenance in a `staged_facts` list property (one JSON string per entry:
    fact, ts, source). No re-embed by default - H576 measured the re-embed as
    inoperative for the render-survival flip and harmful in bulk. `reembed=True`
    re-embeds the updated description via `embed_fn` and writes the new vector.
    """
    stamp = timestamp or datetime.now(timezone.utc).isoformat()
    marker = json.dumps({"fact": fact_text, "ts": stamp, "source": source})
    with driver.session() as session:
        record = session.run(
            "MATCH (e:Entity {id: $id}) "
            "SET e.description = CASE "
            "WHEN e.description IS NULL OR e.description = '' THEN $fact "
            "ELSE e.description + $nl + $fact END, "
            "e.staged_facts = coalesce(e.staged_facts, []) + [$marker] "
            "RETURN e.id AS id, e.description AS description",
            id=anchor_id,
            fact=fact_text,
            nl="\n",
            marker=marker,
        ).single()
        if record is None:
            raise ValueError(f"anchor entity {anchor_id!r} not found")
        reembedded = False
        if reembed:
            if embed_fn is None:
                raise ValueError("reembed=True requires embed_fn")
            vector = embed_fn(record["description"])
            session.run(
                "MATCH (e:Entity {id: $id}) SET e.embedding = $emb",
                id=anchor_id,
                emb=list(vector),
            ).consume()
            reembedded = True
    emit("repair.staged", anchor=anchor_id, reembedded=reembedded)
    return {"anchor": anchor_id, "staged": fact_text, "reembedded": reembedded}
