# -- builder stage: build the wheel ----------------------------------
FROM python:3.11-slim AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN pip install --no-cache-dir build hatchling

WORKDIR /src
COPY . /src
RUN python -m build --wheel --no-isolation

# -- runtime stage: minimal production image ---------------------------
FROM python:3.11-slim AS runtime

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        git \
        gnupg \
    && install -m 0755 -d /etc/apt/keyrings \
    && curl -fsSL https://download.docker.com/linux/debian/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg \
    && chmod a+r /etc/apt/keyrings/docker.gpg \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/debian $(. /etc/os-release; echo $VERSION_CODENAME) stable" > /etc/apt/sources.list.d/docker.list \
    && apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        docker-ce-cli \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir uv

COPY --from=builder /src/dist/*.whl /tmp/
COPY --from=builder /src/pyproject.toml /tmp/

RUN uv pip install --system --no-cache-dir "$(echo /tmp/*.whl)[dev,judge,langgraph,pydanticai]" \
    && rm -rf /tmp/*.whl /tmp/pyproject.toml

RUN groupadd --system evalforge \
    && useradd --system --no-create-home --gid evalforge evalforge

WORKDIR /app
COPY scenarios/ /app/scenarios/
RUN chown -R evalforge:evalforge /app

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD ["evalforge", "version"]

LABEL org.opencontainers.image.title="EvalForge" \
      org.opencontainers.image.description="Framework-agnostic evaluation harness for tool-using AI agents" \
      org.opencontainers.image.source="https://github.com/deghosal-2026/agent-eval-forge" \
      org.opencontainers.image.licenses="MIT" \
      org.opencontainers.image.vendor="deghosal-2026"

USER evalforge
ENTRYPOINT ["evalforge"]
CMD ["--help"]