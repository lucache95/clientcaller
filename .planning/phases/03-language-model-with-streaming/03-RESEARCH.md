# Phase 3 Research: Language Model with Streaming

## Domain: LLM Integration via vLLM + OpenAI-Compatible API

### Technology Stack

**Model:** Gemma 3 27B Instruction-Tuned (`google/gemma-3-27b-it`)
- 27B parameters, bfloat16
- 128K context window, 8192 max output tokens
- Multimodal (text + image input), text output
- Gated model — requires HuggingFace token

**Serving:** vLLM via RunPod Serverless
- Pre-built RunPod template: `runpod/worker-v1-vllm`
- OpenAI-compatible API endpoint
- A100 80GB GPU (~$1.64/hr secure, ~$1.19/hr community)
- Endpoint URL format: `https://api.runpod.ai/v2/<ENDPOINT_ID>/openai/v1`

**Client:** openai Python package (v2.21.0+)
- `AsyncOpenAI` with custom `base_url` pointing to vLLM
- Streaming via `stream=True` returns SSE chunks
- `api_key` = RunPod API key (or "EMPTY" for local)

### Key Patterns

**Pattern 1: OpenAI-Compatible Streaming Client**
```python
from openai import AsyncOpenAI

client = AsyncOpenAI(
    api_key=os.environ["RUNPOD_API_KEY"],
    base_url=f"https://api.runpod.ai/v2/{endpoint_id}/openai/v1",
)

stream = await client.chat.completions.create(
    model="google/gemma-3-27b-it",
    messages=[...],
    stream=True,
    max_tokens=256,
    temperature=0.7,
)

async for chunk in stream:
    delta = chunk.choices[0].delta
    if delta.content:
        yield delta.content  # Token-by-token streaming
```

**Pattern 2: Conversation History Management**
- Per-call conversation history list
- System prompt defines AI personality/behavior
- User messages from STT final transcripts
- Assistant messages from LLM responses
- Context window management (trim oldest messages if too long)

**Pattern 3: vLLM-Specific Parameters**
```python
extra_body={
    "top_k": 50,
    "repetition_penalty": 1.1,
}
```

### Architecture Decisions

1. **AsyncOpenAI over sync**: FastAPI is async, must not block event loop
2. **Shared client, per-call history**: Client is stateless (connection pooling), history is per-call state
3. **Token-by-token streaming**: Each chunk yields immediately for future TTS streaming (Phase 4)
4. **Configurable base_url**: Supports local vLLM, RunPod, or any OpenAI-compatible endpoint
5. **For development**: Use a mock/small model or any OpenAI-compatible API for testing without GPU

### Memory Requirements

- Gemma 3 27B bfloat16: ~54-70GB VRAM
- With FP8 quantization: ~35-45GB VRAM
- Recommended: A100 80GB with `--max-model-len 8192 --gpu-memory-utilization 0.90`

### Latency Budget

Per PROJECT.md: Sub-500ms total response time
- STT: ~200ms (Phase 2)
- **LLM TTFT: ~100-200ms target** (time to first token)
- TTS: ~150ms (Phase 4)
- Network: ~50ms

Gemma 3 27B TTFT on A100: ~200-800ms depending on context length and quantization.
Decision point noted in STATE.md: if TTFT > 400ms, may need Gemma 9B or commercial API.

### RunPod Deployment Config

```
MODEL_NAME=google/gemma-3-27b-it
HF_TOKEN=hf_xxxxx
MAX_MODEL_LEN=8192
GPU_MEMORY_UTILIZATION=0.90
DTYPE=bfloat16
TENSOR_PARALLEL_SIZE=1
MAX_CONCURRENCY=30
```

### Open Questions

1. **System prompt tuning**: What personality/behavior should the AI have? (Can be configured later)
2. **Context window management**: When to trim history? Token counting vs message count?
3. **TTFT validation**: Need to benchmark actual TTFT on RunPod A100 with Gemma 27B
4. **Fallback strategy**: If TTFT too slow, switch to Gemma 9B or use commercial API?
