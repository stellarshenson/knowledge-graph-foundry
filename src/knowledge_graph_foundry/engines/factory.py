"""Engine factory - config selects the engine, the pipeline never knows which."""

from __future__ import annotations

from knowledge_graph_foundry.engines.base import Engine, EngineError
from knowledge_graph_foundry.settings import LLMSettings


def create_engine(cfg: LLMSettings) -> Engine:
    if cfg.engine == "frontier":
        from knowledge_graph_foundry.engines.frontier import FrontierEngine

        return FrontierEngine(cfg)
    if cfg.engine == "claude-cli":
        from knowledge_graph_foundry.engines.claude_cli import ClaudeCliEngine

        return ClaudeCliEngine(cfg)
    if cfg.engine == "local-gpu":
        from knowledge_graph_foundry.engines.local_gpu import LocalGpuEngine

        return LocalGpuEngine(cfg)
    raise EngineError(f"unknown engine: {cfg.engine}")
