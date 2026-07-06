"""R4 LLM defer judge: resolve the 0.4-0.6 posterior band with an LLM.

A pair the Bayesian model cannot decide (a "defer") is described to the engine
by name, type and description; the engine returns a structured verdict of
whether the two records denote the same real-world entity.
"""

from __future__ import annotations

from pydantic import BaseModel

from knowledge_graph_foundry.engines.base import Engine
from knowledge_graph_foundry.models import Entity

_SYSTEM = (
    "You are an entity resolution judge. Decide whether two entity records "
    "refer to the same real-world entity."
)


class MatchVerdict(BaseModel):
    same: bool
    reason: str = ""


def judge_pair(left: Entity, right: Entity, engine: Engine) -> bool:
    """Ask the engine whether `left` and `right` are the same entity."""
    prompt = (
        "Are these two entities the same real-world entity?\n\n"
        f"Entity A:\n  name: {left.name}\n"
        f"  type: {', '.join(left.types)}\n"
        f"  description: {left.description}\n\n"
        f"Entity B:\n  name: {right.name}\n"
        f"  type: {', '.join(right.types)}\n"
        f"  description: {right.description}\n\n"
        "Set same=true only if they denote the identical real-world entity."
    )
    messages = [
        {"role": "system", "content": _SYSTEM},
        {"role": "user", "content": prompt},
    ]
    return engine.complete(messages, MatchVerdict).same
