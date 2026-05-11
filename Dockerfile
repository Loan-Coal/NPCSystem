FROM python:3.11-slim

WORKDIR /app

# Copy dependency manifest first for better layer caching:
# this layer only rebuilds when pyproject.toml or src/ changes.
COPY pyproject.toml ./
COPY src/ ./src/
RUN pip install --no-cache-dir .

# Copy remaining runtime files (prompts, config yamls, .env, etc.)
COPY . .

EXPOSE 8000

CMD ["uvicorn", "npc_engine.main:app", "--host", "0.0.0.0", "--port", "8000"]
