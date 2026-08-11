# Integration Test Results — v0.2.0 (dev-0.2.0)

**Date:** 2026-08-10  
**Branch:** `dev-0.2.0`  
**Commit:** `e93ace8`  
**Host OS:** macOS 15 (arm64)  
**Python:** 3.11.15  
**Model Backend:** omlx (Qwen3.5-4B-4bit + Qwen3.5-9B-MLX-4bit @ localhost:8000)

---

## Summary

| Scope | Result |
|-------|--------|
| **Full test suite** | ✅ 1,319 passed, 0 failed, 0 errored |
| **Non-Docker suite** | ✅ 1,312 passed, 0 failed |
| **Docker container tests** | ✅ 7/7 passed |
| **LLM-as-judge (omlx)** | ✅ 10/10 passed |
| **LLM-backed adapter smoke tests** | ✅ 8/8 passed (smolagents, autogen, llamaindex, adk) |
| **Docker + LLM** (omlx from container) | ✅ 1/1 passed |

---

## Pre-Release Gate Status

| Gate | Status |
|------|--------|
| Full test suite (`pytest`) | ✅ 1,319/1,319 pass |
| `ruff check` | ✅ 0 errors |
| `mypy --strict` | ✅ 0 errors |
| LLM-as-judge (omlx, real model inference) | ✅ 10/10 pass |
| LLM-backed adapter tests (omlx) | ✅ 8/8 pass |
| Docker container security | ✅ 6/6 pass |
| Docker + LLM integration | ✅ 1/1 pass |
| **All Docker + LLM tests** | ✅ **7/7 pass** |