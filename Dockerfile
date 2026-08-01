# Minimal image for sandbox tests and containerized eval runs
FROM python:3.11-slim

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Install uv for reproducible installs
RUN pip install --no-cache-dir uv

WORKDIR /app

# Copy project
COPY . /app

# Install dependencies (including optional adapters for integration tests)
RUN uv sync --extra dev --extra judge --extra langgraph --extra pydanticai

CMD ["bash"]
