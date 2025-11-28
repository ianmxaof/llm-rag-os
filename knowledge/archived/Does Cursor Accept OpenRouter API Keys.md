---
tags:
  - openrouter-api
  - api-keys
  - cursor-app
  - coding-models
  - free-tier
---

**

### Does Cursor Accept OpenRouter API Keys?

Yes, Cursor fully supports OpenRouter API keys through its OpenAI-compatible endpoint setup. This lets you route requests to OpenRouter's ecosystem of models (including free ones) without native integration hassles. It's a popular workaround for accessing diverse LLMs in Cursor's Composer, inline edits (Cmd/Ctrl + K), and chat features.

  

### How to Leverage OpenRouter with Free Tier API Keys in Cursor

OpenRouter's free tier gives you access to select models with generous daily limits (e.g., 10k-100k tokens/day depending on the model, resetting at midnight UTC—no credit card needed). The "master" API key from OpenRouter acts as a unified gateway: Generate one at openrouter.ai/settings/keys (free signup), and it works across any OpenAI-compatible app, including Cursor, VS Code extensions, or custom scripts. Limits apply per model, but you can switch seamlessly.

  

Here's the quick setup in Cursor (tested as of Nov 2025):

1. **Get Your OpenRouter Key**: Head to [openrouter.ai](https://openrouter.ai/settings/keys), sign up/log in, and create a free API key (starts with `sk-or-...`).

2. **Configure in Cursor**:

   - Open Settings (Cmd/Ctrl + ,) > Models tab.

   - Under "OpenAI API Key", paste your OpenRouter key.

   - Enable "Override OpenAI Base URL" and set it to `https://openrouter.ai/api/v1` (no trailing slash).

   - Restart Cursor or refresh the models list.

3. **Add Free Models**: In the Models dropdown, search/add them manually (e.g., `deepseek/deepseek-coder-v2:free`). Disable paid defaults to prioritize free routing. Auto mode will pick based on task, but you can force via prompts like "Use DeepSeek Coder for this refactor."

4. **Leverage in Workflows**:

   - **Inline Edits**: Select code > Cmd/Ctrl + K > Pick a free coding model for quick generations (e.g., debugging loops).

   - **Composer/Chat**: Start sessions with "Optimize this function using Qwen3 Coder" for context-aware suggestions.

   - **Rate Limit Tips**: Monitor usage in OpenRouter dashboard; if you hit caps, fallback to Cursor's built-ins. For high-volume dev, pair with local Ollama via Cursor's custom provider.

   - **Pro Tip**: Use OpenRouter's headers for extras like `HTTP-Referer` (your app name) to track usage, or enable streaming for real-time code previews.

  

This setup turns Cursor into a free-tier powerhouse—expect 2-5x more completions/day vs. stock limits, ideal for prototyping without costs.

  

### Free LLM Models on OpenRouter Scoped for Coding

OpenRouter's free tier (max_price=0) includes ~20-30 models, but I've scoped this list to those optimized for coding: code generation, debugging, agentic tasks (e.g., SWE-Bench scores), or programming reasoning (e.g., HumanEval >50%). These are accessible via your single master key—no per-model auth. Limits vary (e.g., 50k tokens/day for popular ones); check openrouter.ai/models for real-time quotas. Sorted by coding prowess (based on benchmarks like HumanEval/LiveCodeBench).

  

- **google/gemini-2.5-pro-exp-03-25:free**  

  Provider: Google | Params: ~300-500B | Context: 1M tokens  

  Strengths: Top-tier code gen with dependencies (HumanEval: 94.2%); excels at scientific/programming math, long-context refactors.

  

- **meta-llama/llama-4-maverick:free**  

  Provider: Meta | Params: 400B (17B active MoE) | Context: 256k tokens  

  Strengths: Complex symbolic reasoning/code (HumanEval: 88.5%); great for multi-file edits, algo design.

  

- **meta-llama/llama-4-scout:free**  

  Provider: Meta | Params: 109B (17B active MoE) | Context: 512k tokens  

  Strengths: High-context programming (HumanEval: 84.9%); ideal for repo-scale analysis, dependency-heavy tasks.

  

- **qwen/qwen3-coder-480b-a35b:free**  

  Provider: Alibaba/Qwen | Params: 480B MoE (35B active) | Context: 128k+ tokens  

  Strengths: Agentic coding (function calling, tool use); tops LiveCodeBench/SWE-Bench for real-world software eng.

  

- **moonshotai/kimi-k2-0711:free**  

  Provider: Moonshot AI | Params: 1T MoE (32B active) | Context: 128k tokens  

  Strengths: Code synthesis/reasoning (strong on SWE-Bench, LiveCodeBench); agentic workflows like compile-run-fix loops.

  

- **minimax/minimax-m2:free**  

  Provider: MiniMax | Params: 230B MoE (10B active) | Context: 128k tokens  

  Strengths: End-to-end coding (SWE-Bench Verified: high scores); multi-file editing, test-validated repairs, low-latency dev.

  

- **qwen/qwen3-235b-a22b:free**  

  Provider: Alibaba/Qwen | Params: 235B MoE (22B active) | Context: 32k-131k tokens  

  Strengths: "Thinking" mode for math/code (advanced instruction-following); tool-calling for debugging/automation.

  

- **kwaipilot/kat-coder-pro-v1:free**  

  Provider: KwaiPilot | Params: Undisclosed (agentic focus) | Context: 128k tokens  

  Strengths: Real-world software eng (73% on agentic benchmarks); tool-use, multi-turn coding, generalization.

  

- **mistralai/mistral-small-3.1-24b-instruct:free**  

  Provider: Mistral AI | Params: 24B | Context: 96k tokens  

  Strengths: Function calling/JSON for APIs (HumanEval: 79.3%); structured code outputs, mid-scale projects.

  

- **deepseek/deepseek-v3-base:free**  

  Provider: DeepSeek | Params: Undisclosed | Context: 128k tokens  

  Strengths: Technical domains/programming assistance; precise code gen with domain knowledge.

  

- **deepseek/deepseek-r1-zero:free**  

  Provider: DeepSeek | Params: Undisclosed | Context: 128k tokens  

  Strengths: Technical reasoning/debugging; math formulations for algo-heavy code.

  

- **nvidia/llama-3.1-nemotron-nano-8b-v1:free**  

  Provider: NVIDIA | Params: 8B | Context: 8k tokens  

  Strengths: Efficient inference for code (HumanEval: 65.3%); lightweight prototyping, edge devices.

  

- **nousresearch/deephermes-3-llama-3-8b-preview:free**  

  Provider: Nous Research | Params: 8B | Context: 128k tokens  

  Strengths: Instruction-following in code (HumanEval: 55.9%); general dev tasks on constrained setups.

  

Load any via the model ID in Cursor (e.g., prompt "Use gemini-2.5-pro-exp-03-25:free for this"). Start with Gemini or Qwen3 for heavy lifting—they punch above free-tier weight. If you hit limits, rotate models. Ping if setup snags!

**