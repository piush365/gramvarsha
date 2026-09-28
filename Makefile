# GramVarsha: common tasks. Needs Python 3.12 (via uv) and Node 20+.
PY      := .venv/bin/python
UVICORN := .venv/bin/uvicorn

.PHONY: setup data dataset train evaluate retrain test api web dev snapshot docker lint

setup:                 ## create the Python env and install everything
	uv venv --python 3.12 .venv
	uv pip install --python .venv -r ml/requirements.txt -r backend/requirements.txt httpx
	cd frontend && npm ci

data:                  ## re-download all open data into data/ (slow; cached data is committed)
	$(PY) scripts/fetch_data.py

dataset:
	$(PY) -m ml.build_dataset

train: dataset         ## fit kriging + XGBoost -> ml/models/
	$(PY) -m ml.train

evaluate:              ## held-out metrics -> ml/metrics.json (prints the table)
	$(PY) -m ml.evaluate

retrain: train evaluate snapshot

test:
	$(PY) -m pytest -q tests

lint:
	cd frontend && npx tsc --noEmit && npx eslint src

api:                   ## FastAPI on :8000
	$(UVICORN) backend.main:app --reload --port 8000

web:                   ## Next.js on :3000 (talks to NEXT_PUBLIC_API_URL, default localhost:8000)
	cd frontend && npm run dev

dev:                   ## API + web together; Ctrl-C stops both
	@trap 'kill 0' INT TERM; $(UVICORN) backend.main:app --reload --port 8000 & (cd frontend && npm run dev) & wait

snapshot:              ## regenerate the offline fallback in frontend/public/
	$(PY) scripts/make_snapshot.py

docker:                ## build and run the API image locally on :7860
	docker build -f backend/Dockerfile -t gramvarsha-api .
	docker run --rm -p 7860:7860 gramvarsha-api
