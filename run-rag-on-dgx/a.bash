docker run --gpus all \
  -v ~/.cache/huggingface:/root/.cache/huggingface \
  -v ~/Qwen3-Embedding-8B:/model \
  -p 8001:8000 --ipc=host \
  ghcr.nju.edu.cn/nvidia-ai-iot/vllm:0.16.0-g15d76f74e-r38.2-arm64-sbsa-cu130-24.04 \
  vllm serve /model \
  --task embed \
  --trust-remote-code \
  --max-model-len 32768 \
  --quantization fp8 \
  --kv-cache-dtype fp8