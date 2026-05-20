FROM python:3.11-slim

WORKDIR /app

# Layer 1: dependency manifest only — cache key is pyproject.toml, not source files.
COPY pyproject.toml ./

# Layer 2: stub package so pip can resolve and download all deps without the real source.
RUN mkdir -p src/npc_engine && touch src/npc_engine/__init__.py

# Layer 3: install all dependencies via editable link to /app/src.
# This layer only re-runs when pyproject.toml changes, not on source code edits.
RUN pip install --no-cache-dir -e .

# Layer 4: overwrite stub with real source code (invalidated on code changes; layer 3 stays cached).
COPY src/ ./src/

# Layer 5: remaining runtime files (prompts, config yamls, .env, etc.)
COPY . .

EXPOSE 8000

CMD ["uvicorn", "npc_engine.main:app", "--host", "0.0.0.0", "--port", "8000"]
