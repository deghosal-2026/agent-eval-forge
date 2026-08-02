# Support

## Getting Help

- **Documentation:** See `docs/` directory for guides on scoring, scenarios, adapters, and CI integration.
- **Quickstart:** See `README.md` or run `examples/quickstart_agent.py`.
- **GitHub Issues:** Report bugs or request features at [github.com/deghosal-2026/agent-eval-forge/issues](https://github.com/deghosal-2026/agent-eval-forge/issues).

## Common Issues

### "OPENAI_API_KEY is required"

Set your API key:
```bash
export OPENAI_API_KEY=sk-or-v1-...
```

### "Model 'gpt-4o-mini' not found"

Use a valid model name. For OpenRouter, prefix with `openai/`:
```bash
evalforge run --judge openai/gpt-4o-mini ...
```

### "No module named 'langgraph'"

Install optional extras:
```bash
pip install agent-eval-forge[langgraph]
```

### Tests skipping

Tests requiring external services (live LLMs, Docker, MLX) skip automatically. Set:
- `OPENAI_API_KEY` for OpenAI judge tests
- `PYDANTIC_AI_GATEWAY_API_KEY` for PydanticAI Gateway tests
