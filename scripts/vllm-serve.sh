#!/usr/bin/env bash
# Relaunch the shared gpt-oss-120b vLLM server on GPU 1 (port 8010).
# Recovered incantation 2026-07-08 after the 12:20Z SIGTERM outage.
# CRITICAL: CUDA_HOME must be the vllm venv's OWN nvidia/cu13 (has curand.h);
# the separate cuda13 venv wheel set is incomplete for FlashInfer JIT.
# If a prior launch failed with wrong env, purge the poisoned JIT cache first:
#   rm -rf ~/.cache/flashinfer/0.6.12/120f/cached_ops/sampling
cd /home/lab/workspace/learning/projects/knowledge-graph-foundry
setsid nohup env \
  CUDA_DEVICE_ORDER=PCI_BUS_ID CUDA_VISIBLE_DEVICES=1 HF_HUB_OFFLINE=1 \
  VLLM_USE_DEEP_GEMM=0 VLLM_MOE_USE_DEEP_GEMM=0 VLLM_WSL2_ENABLE_PIN_MEMORY=1 \
  VLLM_USE_FLASHINFER_SAMPLER=0 \
  CUDA_HOME=/home/lab/venvs/vllm/lib/python3.12/site-packages/nvidia/cu13 \
  PATH=/home/lab/venvs/vllm/bin:/home/lab/venvs/vllm/lib/python3.12/site-packages/nvidia/cu13/bin:/opt/conda/envs/cudabuild/bin:/usr/bin:/bin \
  CC=/opt/conda/envs/cudabuild/bin/gcc CXX=/opt/conda/envs/cudabuild/bin/g++ \
  NVCC_PREPEND_FLAGS='-ccbin /opt/conda/envs/cudabuild/bin/g++' \
  CPATH=/home/lab/venvs/pyinc \
  /home/lab/venvs/vllm/bin/vllm serve openai/gpt-oss-120b --port 8010 --max-model-len 32768 \
  --served-model-name gpt-oss-120b --gpu-memory-utilization 0.9 \
  >> logs/vllm-server.log 2>&1 &
echo "vllm launching detached; watch logs/vllm-server.log; health: curl -s http://localhost:8010/v1/models"
