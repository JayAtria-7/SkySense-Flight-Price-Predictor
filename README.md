# FlightIQ - AI Flight Price Predictor

A production-ready AI-powered flight price prediction system. It includes:

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
