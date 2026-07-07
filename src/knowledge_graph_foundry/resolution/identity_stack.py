"""R15-H158 v2 identity decision stack (shipped behind resolution.identity_stack).

Three mechanisms decided offline on the H101 298-pair adjudicated benchmark:

1. isotonic-calibrated Titan cosine (H129, ECE 0.050) - raw embedding cosine
   mapped to a probability via a versioned support curve;
2. logistic arbitration (H106, F1 0.811) - a logistic over the deployable
   feature set [name_id, calibrated_cosine, nli_contra, posterior], coefficients
   fit offline and baked into the artifact (never refit at runtime);
3. GLOBAL NLI contradiction veto (H128, 83% false-merge cut) - mDeBERTa
   sibling-contradiction check that forces a block on any would-be merge.

The Bayesian posterior is retired from the decision but kept as a logistic
feature (H54: the description-LR term is load-bearing for coverage). The NLI
model is lazy-loaded only when v2 is active, on CUDA if available else CPU.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Optional

from loguru import logger

from knowledge_graph_foundry.models import Entity, normalize_name
from knowledge_graph_foundry.resolution.similarity import cosine_similarity

_RECORD_CAP = 512  # char cap on the NLI premise/hypothesis render (offline convention)
_GENERIC_TYPES = {"Entity"}


def _interp(x_points: list[float], y_points: list[float], value: float) -> float:
    """Piecewise-linear interpolation on a monotone support curve (clip at ends)."""
    if not x_points:
        return value
    if value <= x_points[0]:
        return y_points[0]
    if value >= x_points[-1]:
        return y_points[-1]
    lo, hi = 0, len(x_points) - 1
    while lo < hi - 1:
        mid = (lo + hi) // 2
        if x_points[mid] <= value:
            lo = mid
        else:
            hi = mid
    x0, x1 = x_points[lo], x_points[hi]
    if x1 == x0:
        return y_points[lo]
    t = (value - x0) / (x1 - x0)
    return y_points[lo] + t * (y_points[hi] - y_points[lo])


def _render(entity: Entity) -> str:
    """NLI record text: `Type: name - description | specs` (offline `fields` convention)."""
    typ = next((t for t in entity.types if t not in _GENERIC_TYPES), "Entity")
    text = f"{typ}: {entity.name}"
    if entity.description:
        text += f" - {entity.description}"
    specs = [f"{k}: {v}" for k, v in entity.properties.items() if v not in (None, "", [])]
    if specs:
        text += " | " + "; ".join(specs)
    return text[:_RECORD_CAP]


class V2IdentityStack:
    """Loads the baked v2 artifact and decides candidate pairs.

    `nli_contra_batch` runs the entailment model once over every candidate pair;
    `decide` then applies the logistic and the veto per pair using the cached
    contradiction score.
    """

    def __init__(self, artifact: dict, veto_threshold: float):
        iso = artifact["isotonic"]
        self._iso_x = iso["x"]
        self._iso_y = iso["y"]
        log = artifact["logistic"]
        self._feature_order: list[str] = log["feature_order"]
        self._weights: list[float] = log["weights"]
        self._intercept: float = log["intercept"]
        self._threshold: float = log["threshold"]
        self._defer_lower: float = log.get("defer_lower", self._threshold * 0.5)
        self._nli_model_id: str = artifact["nli"]["model"]
        self._veto_threshold = veto_threshold
        self._nli = None  # lazy (tokenizer, model, device, contra/entail indices)

    @classmethod
    def load(cls, path: str | Path, veto_threshold: float) -> "V2IdentityStack":
        artifact = json.loads(Path(path).read_text())
        return cls(artifact, veto_threshold)

    def calibrated_cosine(self, cosine: float) -> float:
        return _interp(self._iso_x, self._iso_y, cosine)

    # -- NLI (lazy) ---------------------------------------------------------
    def _ensure_nli(self) -> None:
        if self._nli is not None:
            return
        import torch  # noqa: PLC0415
        from transformers import (  # noqa: PLC0415
            AutoModelForSequenceClassification,
            AutoTokenizer,
        )

        device = "cuda" if torch.cuda.is_available() else "cpu"
        tok = AutoTokenizer.from_pretrained(self._nli_model_id)
        model = AutoModelForSequenceClassification.from_pretrained(self._nli_model_id)
        model = model.to(device).eval()
        id2label = model.config.id2label
        con_ix = next(k for k, v in id2label.items() if "contradict" in v.lower())
        self._nli = (tok, model, device, con_ix)
        logger.info("v2 identity stack: NLI model {} loaded on {}", self._nli_model_id, device)

    def nli_contra_batch(self, pairs: list[tuple[Entity, Entity]], batch_size: int = 32) -> list[float]:
        """Symmetric contradiction score max(contra(a->b), contra(b->a)) per pair."""
        if not pairs:
            return []
        self._ensure_nli()
        import torch  # noqa: PLC0415

        tok, model, device, con_ix = self._nli
        left = [_render(a) for a, _ in pairs]
        right = [_render(b) for _, b in pairs]

        def _contra(premises: list[str], hypotheses: list[str]) -> list[float]:
            out: list[float] = []
            with torch.no_grad():
                for i in range(0, len(premises), batch_size):
                    enc = tok(
                        premises[i : i + batch_size],
                        hypotheses[i : i + batch_size],
                        truncation=True,
                        max_length=256,
                        padding=True,
                        return_tensors="pt",
                    ).to(device)
                    probs = torch.softmax(model(**enc).logits, dim=-1)
                    out.extend(probs[:, con_ix].cpu().tolist())
            return out

        c_ab = _contra(left, right)
        c_ba = _contra(right, left)
        return [max(x, y) for x, y in zip(c_ab, c_ba)]

    # -- decision -----------------------------------------------------------
    def _features(
        self,
        a: Entity,
        b: Entity,
        posterior: float,
        nli_contra: float,
        cosine: Optional[float] = None,
    ) -> dict[str, float]:
        cos = cosine
        if cos is None:
            cos = 0.0
            if a.embedding and b.embedding:
                cos = cosine_similarity(a.embedding, b.embedding)
        name_id = 1.0 if normalize_name(a.name) == normalize_name(b.name) else 0.0
        return {
            "name_id": name_id,
            "calibrated_cosine": self.calibrated_cosine(cos),
            "nli_contra": nli_contra,
            "posterior": posterior,
        }

    def score(
        self,
        a: Entity,
        b: Entity,
        posterior: float,
        nli_contra: float,
        cosine: Optional[float] = None,
    ) -> float:
        feats = self._features(a, b, posterior, nli_contra, cosine)
        z = self._intercept + sum(
            w * feats[name] for w, name in zip(self._weights, self._feature_order)
        )
        return 1.0 / (1.0 + math.exp(-z))

    def decide(
        self,
        a: Entity,
        b: Entity,
        posterior: float,
        nli_contra: float,
        cosine: Optional[float] = None,
    ) -> tuple[str, float, bool]:
        """Return (verdict, logistic_score, vetoed). A would-be merge whose
        contradiction score crosses the veto threshold is forced to block.
        `cosine` overrides the embedding cosine when one side carries no
        vector (the live-graph match path derives it from the index score)."""
        s = self.score(a, b, posterior, nli_contra, cosine)
        if s >= self._threshold:
            if nli_contra >= self._veto_threshold:
                return "block", s, True
            return "merge", s, False
        if s >= self._defer_lower:
            return "defer", s, False
        return "block", s, False
