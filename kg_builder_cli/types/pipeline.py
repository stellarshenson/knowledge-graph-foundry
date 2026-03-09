"""Pipeline models for kg-builder-cli."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from .config import AppConfig


class PipelineEvent(BaseModel):
    stage: str
    document_idx: int = 0
    chunk_idx: int = 0
    entity_count: int = 0
    timestamp: datetime = Field(default_factory=datetime.now)


class PipelineStats(BaseModel):
    documents_processed: int = 0
    chunks_processed: int = 0
    entities_extracted: int = 0
    relationships_extracted: int = 0
    facts_extracted: int = 0
    llm_calls: int = 0
    tokens_used: int = 0


class RunReport(BaseModel):
    config_snapshot: Optional[AppConfig] = None
    stats: PipelineStats = PipelineStats()
    events: list[PipelineEvent] = Field(default_factory=list)
    decisions: list[str] = Field(default_factory=list)
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
