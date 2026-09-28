# GramVarsha API. Build from the REPO ROOT:  docker build -f backend/Dockerfile -t gramvarsha-api .
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PORT=7860
WORKDIR /app

# libgomp: OpenMP runtime needed by XGBoost
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

# Only what serving needs: code, trained models, metrics, small static data.
COPY ml/__init__.py ml/features.py ml/kriging.py ml/model.py ml/physics.py ml/explain.py ml/metrics.json ml/
COPY ml/models ml/models
COPY data/manifest.json data/panchayats.csv data/terrain.csv data/village_names.csv data/*.geojson data/
COPY backend backend

# Hugging Face Spaces runs containers as uid 1000 and expects port 7860.
RUN useradd -m -u 1000 app && mkdir -p backend/cache && chown -R app /app
USER app
EXPOSE 7860
CMD ["sh", "-c", "uvicorn backend.main:app --host 0.0.0.0 --port ${PORT}"]
