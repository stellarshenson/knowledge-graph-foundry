"""Tests for LLM engines - claude CLI subprocess mocked, factory dispatch."""

import json
from unittest.mock import MagicMock, patch

import pytest
from pydantic import BaseModel

from knowledge_graph_foundry.engines import EngineError, create_engine
from knowledge_graph_foundry.engines.claude_cli import ClaudeCliEngine, _extract_json
from knowledge_graph_foundry.settings import LLMSettings


class Answer(BaseModel):
    value: int
    label: str


def _proc(stdout: str, returncode: int = 0, stderr: str = ""):
    m = MagicMock()
    m.stdout = stdout
    m.returncode = returncode
    m.stderr = stderr
    return m


class TestExtractJson:
    def test_plain_object(self):
        assert json.loads(_extract_json('{"a": 1}')) == {"a": 1}

    def test_fenced_object(self):
        assert json.loads(_extract_json('```json\n{"a": 1}\n```')) == {"a": 1}

    def test_prose_wrapped(self):
        assert json.loads(_extract_json('Here you go: {"a": 1} hope it helps')) == {"a": 1}

    def test_no_json_raises(self):
        with pytest.raises(ValueError):
            _extract_json("no json here")


class TestClaudeCliEngine:
    def test_valid_json_first_try(self):
        engine = ClaudeCliEngine(LLMSettings(engine="claude-cli"))
        with patch("subprocess.run", return_value=_proc('{"value": 7, "label": "ok"}')) as run:
            result = engine.complete([{"role": "user", "content": "count"}], Answer)
        assert result == Answer(value=7, label="ok")
        prompt = run.call_args.args[0][2]
        assert "JSON schema" in prompt

    def test_repair_reprompt_on_invalid(self):
        engine = ClaudeCliEngine(LLMSettings(engine="claude-cli"))
        outputs = [_proc("garbage no json"), _proc('{"value": 3, "label": "fixed"}')]
        with patch("subprocess.run", side_effect=outputs):
            result = engine.complete([{"role": "user", "content": "count"}], Answer)
        assert result.label == "fixed"

    def test_engine_error_after_repair_fails(self):
        engine = ClaudeCliEngine(LLMSettings(engine="claude-cli"))
        with patch("subprocess.run", return_value=_proc("still garbage")):
            with pytest.raises(EngineError) as exc:
                engine.complete([{"role": "user", "content": "count"}], Answer)
        assert exc.value.raw_output == "still garbage"

    def test_nonzero_exit_raises(self):
        engine = ClaudeCliEngine(LLMSettings(engine="claude-cli"))
        with patch("subprocess.run", return_value=_proc("", returncode=1, stderr="boom")):
            with pytest.raises(EngineError, match="exited 1"):
                engine.complete([{"role": "user", "content": "x"}], Answer)


class TestFactory:
    def test_claude_cli_selected(self):
        engine = create_engine(LLMSettings(engine="claude-cli"))
        assert engine.name == "claude-cli"

    def test_local_gpu_requires_base_url(self):
        with pytest.raises(EngineError, match="base_url"):
            create_engine(LLMSettings(engine="local-gpu"))

    def test_frontier_selected(self):
        engine = create_engine(LLMSettings(engine="frontier"))
        assert engine.name == "frontier"
