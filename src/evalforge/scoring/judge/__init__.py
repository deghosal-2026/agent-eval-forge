"""LLM-as-judge scoring — provider-specific clients and judge-based scorers.

This sub-package provides the infrastructure for using an LLM as an evaluator
("LLM-as-judge") to score agent outputs on subjective or complex criteria.

Modules:
    client  — Abstract base class (:class:`JudgeClient`) for all judge providers.
    scorers — Factory that creates :class:`Scorer` classes for each judge metric,
              each calling a JudgeClient with a scenario-specific prompt.
    openai  — OpenAI-compatible API client (also serves Ollama/LiteLLM with same protocol).
    anthropic — Anthropic Messages API client.
    mlx     — mlx-lm local inference client (Apple Silicon).
    ollama  — Ollama local API client.
    mock    — Mock judge for testing (returns a fixed score).
"""
