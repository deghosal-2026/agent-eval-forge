# CI Strategy for Field Tests

This document defines the CI strategy for running field tests against real-world
LangGraph and PydanticAI agents from public GitHub repositories.

## Principles

1. **Secrets via CI env**: API keys are injected via CI secrets, never committed.
2. **Strict cost/time ceilings**: Each test has a maximum cost and time budget.
3. **Split jobs per suite**: LangGraph and PydanticAI suites run as separate jobs.
4. **Graceful skips**: Tests that can't run (missing deps, no API key) are skipped, never fail.

## CI Job Configuration

### GitHub Actions Matrix

```yaml
field-tests:
  strategy:
    matrix:
      suite: [langgraph, pydantic-ai]
      tier: [local, cheap, better]
    fail-fast: false
  steps:
    - name: Run field tests
      env:
        OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
        OPENROUTER_API_KEY: ${{ secrets.OPENROUTER_API_KEY }}
      run: |
        pytest tests/field/ -m field --tier=${{ matrix.tier }} --suite=${{ matrix.suite }}
```

### Cost & Time Ceilings

| Tier | Model | Max Cost/Scenario | Max Time/Scenario | Max Time/Job |
|------|-------|-------------------|--------------------|--------------|
| local | Qwen/MLX | $0.00 | 30s | 5min |
| cheap | gpt-4o-mini | $0.01 | 30s | 10min |
| better | gpt-4o | $0.05 | 60s | 15min |

### Flake Budget

- **Per test file**: 60-120s timeout
- **Per scenario**: 30s timeout
- **Retry on flake**: 1 retry per scenario
- **Max total failures**: 20% of scenarios before job fails

### Graceful Skips

```python
@pytest.mark.field
def test_agent_langgraph(agent_config):
    if not has_api_key():
        pytest.skip("No API key — skipping field test")
    if not agent_installed():
        pytest.xfail("Agent dependency not installed")
```

## Secrets Management

| Secret | Used By | Required |
|--------|---------|----------|
| `OPENAI_API_KEY` | OpenAI judge + agent | Yes |
| `ANTHROPIC_API_KEY` | Anthropic judge | Optional |
| `OPENROUTER_API_KEY` | OpenRouter routing | Optional |
| `MLX_SERVER_URL` | Local MLX judge | Optional |

Never log or echo secret values. The sandbox mode (`--sandbox`) strips
non-allowlisted env vars from the agent process.

## Cost Monitoring

Use the cost governor to abort runs that exceed budget:

```bash
evalforge run \
  --pack field/scenarios/langgraph-core.yaml \
  --agent isolated:field/agents/lg-chatbot \
  --judge mock \
  --max-cost 1.00 \
  --timeout 30
```

The `--max-cost` flag sets a hard ceiling. If the run exceeds it, remaining
scenarios are marked as `aborted` with reason `cost_exceeded`.

## Split Jobs

Each suite runs independently:

1. **LangGraph suite**: `pytest -m field --suite=langgraph`
2. **PydanticAI suite**: `pytest -m field --suite=pydantic-ai`
3. **Security suite**: `pytest -m field --suite=security`

This allows partial failures (one suite failing doesn't block the others).

## Aggregated Output

Each job produces a JSON summary:

```json
{
  "suite": "langgraph",
  "tier": "cheap",
  "total_agents": 8,
  "passed": 6,
  "failed": 1,
  "skipped": 1,
  "timeouts": 0,
  "total_cost_usd": 0.12,
  "duration_seconds": 180
}
```

Results are uploaded as CI artifacts and aggregated in the GitHub Actions summary.
