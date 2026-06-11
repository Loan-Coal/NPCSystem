FROM python:3.11-slim

WORKDIR /app

# Layer 1: dependency manifest only — cache key is pyproject.toml, not source files.
COPY pyproject.toml ./

# Layer 2: stub package so pip can resolve and download all deps without the real source.
RUN mkdir -p src/npc_engine && touch src/npc_engine/__init__.py

# Layer 3a: CPU-only PyTorch. sentence-transformers requires torch, but the default
# PyPI torch wheel drags in ~2.5 GB of CUDA libraries that are useless in a CPU-only
# container. Installing the CPU build first satisfies the `torch>=2.0.0` requirement
# so the editable install below resolves it as already-present and skips every
# nvidia-* / triton CUDA wheel. Cached independently of the rest of the deps.
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

# Layer 3b: install remaining dependencies via editable link to /app/src.
# This layer only re-runs when pyproject.toml changes, not on source code edits.
RUN pip install --no-cache-dir -e .

# Layer 4: overwrite stub with real source code (invalidated on code changes; layer 3 stays cached).
COPY src/ ./src/

# Layer 5: remaining runtime files (prompts, config yamls, .env, etc.)
COPY . .

EXPOSE 8000

# Build identifier surfaced on GET /health (L9-05) so a stale image is detectable.
# Pass via: docker build --build-arg BUILD_SHA=$(git rev-parse --short HEAD)
ARG BUILD_SHA=dev
ENV BUILD_SHA=$BUILD_SHA

CMD ["uvicorn", "npc_engine.main:app", "--host", "0.0.0.0", "--port", "8000"]
