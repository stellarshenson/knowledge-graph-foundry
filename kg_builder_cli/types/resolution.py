"""Entity resolution models for kg-builder-cli."""

from typing import Optional

from pydantic import BaseModel

from .extraction import Entity


class NormalizationMeta(BaseModel):
    method: str = ""
    score: float = 0.0
    matched_id: Optional[str] = None


class ResolvedEntity(Entity):
    normalized_name: str = ""
    normalized_score: float = 0.0
    normalized_method: str = ""
