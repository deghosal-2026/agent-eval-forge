# Field Test Agent Roster

v0.2.0 field test candidates across 8 OMLX-compatible frameworks (Claude SDK excluded — requires Anthropic API). 19 total agents, shims at `field/config/<slug>_wrapper.py`.

## Round 1 — 19 Agents Across 8 Frameworks

### LangGraph (2)
| Slug | Repo | Self-contained Tools |
|---|---|---|
| lg-azure | Azure-Samples/python-ai-agent-frameworks-demos | play_song stubs |
| lg-official | langchain-ai/langgraph | react agent, code assistant |

### PydanticAI (2)
| Slug | Repo | Self-contained Tools |
|---|---|---|
| pai-azure | Azure-Samples/python-ai-agent-frameworks-demos | weather stub, activities stub, date |
| pai-official | pydantic/pydantic-ai | bank_support, roulette_wheel |

### CrewAI (3)
| Slug | Repo | Self-contained Tools |
|---|---|---|
| crew-qs | ababdotai/awesome-agent-quickstart | MyCustomTool stub |
| crew-examples | crewAIInc/crewAI-examples | CalculatorTools (AST-based) |
| crew-quickstarts | crewAIInc/crewAI-quickstarts | Guardrails validator |

### OpenAI Agents SDK (2)
| Slug | Repo | Self-contained Tools |
|---|---|---|
| oa-azure | Azure-Samples/python-ai-agent-frameworks-demos | weather, activities, date |
| oa-official | openai/openai-agents-python | shell, code_interpreter, file_search |

### smolagents (3)
| Slug | Repo | Self-contained Tools |
|---|---|---|
| sm-smolcc | aniemerg/smolcc | Bash, Edit, Grep, Glob, LS, Replace, View (REAL tools) |
| sm-deepsearch | lwyBZss8924d/DeepSearchAgents | search, readurl, final_answer (API keys needed for production tools) |
| sm-qs | ababdotai/awesome-agent-quickstart | get_weather |

### AutoGen / AG2 (2)
| Slug | Repo | Self-contained Tools |
|---|---|---|
| ag-azure | Azure-Samples/python-ai-agent-frameworks-demos | weather, activities, date |
| ag-official | ag2ai/ag2 | MCP, RAG, code execution |

### LlamaIndex (2)
| Slug | Repo | Self-contained Tools |
|---|---|---|
| li-azure | Azure-Samples/python-ai-agent-frameworks-demos | QueryEngineTool on local PDFs |
| li-official | run-llama/llama_index | FunctionTool, QueryEngineTool |

### Google ADK (3)
| Slug | Repo | Self-contained Tools |
|---|---|---|
| adk-qs | ababdotai/awesome-agent-quickstart | get_weather, get_current_time |
| adk-sokart | sokart/adk-walkthrough | add, subtract, multiply, divide (REAL tools) |
| adk-official | google/adk-python | built-in example agents |

---

