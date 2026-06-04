# agenthub-runtime:python3.11
#
# Runtime image for AgentHub-deployed Python apps.
# Pre-installs the dependency whitelist defined in
# backend/skills/python_runtime_environment.md (Agents writing code
# can ONLY use libraries listed there - any unlisted import fails to deploy).
#
# Design:
# 1. No CMD - container starts long-running (sleep infinity) and the
#    deploy_app tool triggers actual service startup via docker exec
# 2. WORKDIR /app + sandbox dir mounted here, so relative paths in
#    Agent-written code resolve correctly
# 3. Only essentials for "covers 80% web demo / data-analysis use cases"
#    Image size target: < 500MB

FROM python:3.11-slim

# System packages:
# - libfreetype6 / libpng16-16: matplotlib font + PNG output
# - curl: deploy_app health check
RUN apt-get update && apt-get install -y --no-install-recommends \
        libfreetype6 \
        libpng16-16 \
        ca-certificates \
        curl \
    && rm -rf /var/lib/apt/lists/*

# Pip install: versions MUST stay in sync with
# backend/skills/python_runtime_environment.md
# (any version bump here requires updating the skill, otherwise
# the version Agents see and the version in the container will diverge)
RUN pip install --no-cache-dir \
        # Web frameworks
        "fastapi==0.115.*" \
        "uvicorn[standard]==0.32.*" \
        "flask==3.0.*" \
        "jinja2==3.1.*" \
        python-multipart \
        aiofiles \
        # HTTP
        httpx \
        requests \
        # Storage
        "sqlalchemy==2.0.*" \
        aiosqlite \
        # Data
        "pandas==2.2.*" \
        "numpy==2.0.*" \
        "matplotlib==3.9.*" \
        # Config
        python-dotenv \
        "pydantic==2.*" \
        pydantic-settings

# matplotlib in headless container needs Agg backend
ENV MPLBACKEND=Agg

# Python runtime tweaks
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Sandbox mount point. deploy_app runs:
#   docker run ... -v <host_sandbox>:/app
WORKDIR /app

# Long-running container: starts as sleep infinity,
# deploy_app uses docker exec to start uvicorn etc.
CMD ["sleep", "infinity"]
