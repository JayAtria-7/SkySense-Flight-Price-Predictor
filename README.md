# Flight Price Predictor (UI + API)

A production-ready starter for predicting flight prices using your existing notebook logic. It includes:

- FastAPI backend that loads `Clean_Dataset.csv`, builds a scikit-learn Pipeline, trains a RandomForestRegressor, and exposes `/api/predict`.
- Responsive web UI (no framework) with accessible, validated form, imputation badges, results with uncertainty and contributors, and scenario chips.

## Run locally (Windows, cmd)

```bat
REM 1) Create & activate venv
py -m venv .venv
.venv\Scripts\activate

REM 2) Install dependencies
pip install -r requirements.txt

REM 3) Start the server (serves API and web UI)
uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```

Open http://127.0.0.1:8000 in your browser.

## Deploy

### Option A: Hugging Face Spaces (free, auto-deploy)

This repo includes a GitHub Action that deploys a curated bundle to your Space on every push to `main`.

1) Create a Space (Docker template) on Hugging Face and note: USERNAME and SPACE name.
2) In this repo (GitHub) add a repository Secret named `HF_TOKEN` with a Hugging Face Access Token (Write scope).
3) Ensure the workflow file `.github/workflows/deploy-to-hf.yml` has your `HF_USERNAME` and `SPACE_NAME` (already set in this repo).
4) Push to `main` or re-run the workflow in the Actions tab.

The workflow builds a small bundle (backend/, web/, requirements.txt, Dockerfile, README.md) and pushes only that to the Space, avoiding large CSVs.

Environment variables (set in your Space → Settings → Variables & secrets):
- `DATASET_URL` (optional): URL to your CSV dataset (raw GitHub works). Default points to this repo's CSV.
- `MAX_TRAIN_ROWS` (optional): cap dataset rows for faster, lower-memory training (default 25000).

On first start, the app will try to train from `Clean_Dataset.csv` if present; if not, it will load from `DATASET_URL`. If neither works, it starts with a small dummy model so the API stays responsive.

### Option A: Docker (recommended)

Build and run locally to verify:

```cmd
docker build -t flight-price-predictor .
docker run --rm -p 8000:8000 flight-price-predictor
```

Open http://127.0.0.1:8000/ui/

Deploy to any Docker-capable platform (AWS ECS/Fargate, Azure Web App for Containers, GCP Cloud Run, Fly.io):

- Image name: flight-price-predictor
- Container port: 8000
- Health check path: /api/health

### Option B: Render (no Docker needed)

Use the `render.yaml` in the repo as a Blueprint:
1. Push to GitHub.
2. In Render, "New +" → "Blueprint" → pick this repo.
3. Confirm the defaults; it will build with `pip install -r requirements.txt` and start `uvicorn`.
4. Visit the deployed URL at `/ui/`.

### Option C: Azure App Service (Linux)

1. Create a Web App (Linux) with Python 3.11 runtime.
2. Deploy code (zip deploy or GitHub Action). Ensure `requirements.txt` is at the repo root.
3. Configure Startup Command:
  `uvicorn backend.main:app --host 0.0.0.0 --port 8000`
4. Set App Settings:
  - WEBSITES_PORT=8000
  - PYTHONUNBUFFERED=1
5. Add health check path: `/api/health`.
6. Browse to `/ui/`.

Notes:
- The API trains on startup if `backend/model.joblib` is missing or outdated vs `Clean_Dataset.csv`. For faster cold starts, build the Docker image once and reuse it.
- If you need exact notebook parity, export your trained pipeline (joblib) and place it at `backend/model.joblib` before deployment.
 - In Docker and Spaces, you can control dataset source with `DATASET_URL` and training cost with `MAX_TRAIN_ROWS`.

## API

- GET `/api/metadata`: Allowed categories and defaults.
- GET `/api/health`: Health/status and model version.
- GET `/api/route-median?source_city=Delhi&destination_city=Mumbai`: Route-specific and global median duration.
- POST `/api/predict`: Body fields
  - Required: `source_city`, `destination_city`, `class` (Economy|Business), `stops` (zero|one|two_or_more), `days_left` (int >= 0)
  - Optional: `duration` (hours > 0), `airline`, `departure_time`, `arrival_time`, `flight` (ignored)

Response includes `predicted_price`, `lower_bound`, `upper_bound`, `top_contributors`, `assumptions_used`, and `echo`.

## Notes

- Preprocessing matches notebook:
  - Drop `Unnamed: 0` and `flight` (flight collected in UI but not sent to model features).
  - `class`: Business -> 1, Economy -> 0
  - `stops`: encoded as 0/1/2 for zero/one/two_or_more
  - One-hot for: airline, source_city, departure_time, arrival_time, destination_city
  - `duration`: median-imputed (route-specific median, fallback to global)
- Model is persisted to `backend/model.joblib` after first train; subsequent starts load it if fresher than the CSV for faster startup and stability.
- Uncertainty range is estimated from per-tree variance.
- Top contributors are approximated by toggling feature groups relative to a baseline (fast heuristic).

## Daily ops & enhancements

- Prediction logs are appended to `logs/predictions.csv` (UTC timestamp, anonymized echo without flight number) for quick analysis.
- UI adds:
  - Swap cities button.
  - Live duration hint from route median (shows Imputed badge if used).
  - Scenario comparison table for quick what-ifs.
  - Local fallback values for selects if API metadata is momentarily unavailable.

## Accessibility

- Keyboard accessible, visible focus, ARIA roles on errors and dynamic regions.
- Inline error messages; no color-only indicators.


E:\project\capstone1\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload

## Next steps (optional)

- Persist a trained model artifact from the notebook and load it at startup.
- Add SHAP-based explanations for finer contributions.
- Add admin settings to toggle required fields and defaults.
- Internationalize labels and currency.
