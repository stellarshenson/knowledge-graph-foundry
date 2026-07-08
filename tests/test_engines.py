"""Tests for LLM engines - claude CLI subprocess mocked, factory dispatch."""

import json
import subprocess
import sys
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

    def test_local_gpu_constructs_in_fresh_interpreter(self):
        """DEF-6: client construction must not depend on import order. A fresh
        interpreter with no pre-imports must build the engine without the
        instructor RegistryError the notebooks used to work around."""
        code = (
            "from knowledge_graph_foundry.settings import LLMSettings;"
            "from knowledge_graph_foundry.engines.local_gpu import LocalGpuEngine;"
            "LocalGpuEngine(LLMSettings(engine='local-gpu', "
            "base_url='http://localhost:1/v1'));"
            "print('OK')"
        )
        proc = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
        assert proc.returncode == 0, proc.stderr
        assert "OK" in proc.stdout

    def test_frontier_selected(self):
        engine = create_engine(LLMSettings(engine="frontier"))
        assert engine.name == "frontier"


class TestEngineMatrix:
    """Goal contract: OpenAI API, Anthropic API, Bedrock, vLLM, llama.cpp all route."""

    def _frontier_with_spy(self, cfg):
        engine = create_engine(cfg)
        spy = MagicMock()
        spy.chat.completions.create.return_value = Answer(value=1, label="ok")
        engine._client = spy
        return engine, spy

    def _create_kwargs(self, spy):
        return spy.chat.completions.create.call_args.kwargs

    def test_bedrock_model_string_and_region(self, monkeypatch):
        monkeypatch.delenv("AWS_REGION_NAME", raising=False)
        cfg = LLMSettings(
            engine="frontier",
            model="bedrock/eu.anthropic.claude-sonnet-4-5-20250929-v1:0",
            region="eu-central-1",
        )
        engine, spy = self._frontier_with_spy(cfg)
        engine.complete([{"role": "user", "content": "hi"}], Answer)
        assert self._create_kwargs(spy)["model"].startswith("bedrock/")
        import os

        assert os.environ["AWS_REGION_NAME"] == "eu-central-1"

    def test_anthropic_api_model_string(self):
        cfg = LLMSettings(engine="frontier", model="anthropic/claude-sonnet-4-5")
        engine, spy = self._frontier_with_spy(cfg)
        engine.complete([{"role": "user", "content": "hi"}], Answer)
        assert self._create_kwargs(spy)["model"] == "anthropic/claude-sonnet-4-5"

    def test_openai_api_model_string(self):
        cfg = LLMSettings(engine="frontier", model="openai/gpt-4o")
        engine, spy = self._frontier_with_spy(cfg)
        engine.complete([{"role": "user", "content": "hi"}], Answer)
        assert self._create_kwargs(spy)["model"] == "openai/gpt-4o"

    def test_vllm_endpoint_routing(self):
        cfg = LLMSettings(
            engine="local-gpu",
            model="Qwen/Qwen2.5-14B-Instruct",
            base_url="http://localhost:8000/v1",
        )
        engine, spy = self._frontier_with_spy(cfg)
        engine.complete([{"role": "user", "content": "hi"}], Answer)
        kwargs = self._create_kwargs(spy)
        assert kwargs["model"] == "openai/Qwen/Qwen2.5-14B-Instruct"
        assert kwargs["api_base"] == "http://localhost:8000/v1"

    def test_llamacpp_endpoint_routing(self):
        # llama.cpp llama-server exposes the same OpenAI-compatible surface
        cfg = LLMSettings(
            engine="local-gpu",
            model="qwen2.5-14b-instruct-q4_k_m",
            base_url="http://localhost:8080/v1",
        )
        engine, spy = self._frontier_with_spy(cfg)
        engine.complete([{"role": "user", "content": "hi"}], Answer)
        kwargs = self._create_kwargs(spy)
        assert kwargs["model"] == "openai/qwen2.5-14b-instruct-q4_k_m"
        assert kwargs["api_base"] == "http://localhost:8080/v1"
