from __future__ import annotations
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError
from pathlib import Path
import pandas as pd

from .schemas import PredictRequest, PredictResponse, MetadataResponse
from .pipeline import (
    load_or_train_model,
    ALLOWED_AIRLINES,
    ALLOWED_CITIES,
    ALLOWED_TIMES,
    ALLOWED_STOPS,
    CLASS_MAP,
    STOPS_MAP,
)
from datetime import datetime
import json
from pathlib import Path

app = FastAPI(title="Flight Price Predictor")

# Allow same-origin and localhost during dev
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve static web files from ../web under /ui to avoid shadowing /api
web_dir = Path(__file__).resolve().parents[1] / "web"
if web_dir.exists():
    app.mount("/ui", StaticFiles(directory=web_dir, html=True), name="ui")

@app.get("/")
def root():
    # Redirect root to the UI index for convenience
    # Using a simple HTML redirect to avoid extra dependencies
    return {
        "message": "Flight Price Predictor API. Open /ui/ for the web app.",
        "endpoints": ["/api/metadata", "/api/predict", "/ui/"],
    }


@app.on_event("startup")
def _startup():
    load_or_train_model()


@app.get("/api/metadata", response_model=MetadataResponse)
def metadata():
    model = load_or_train_model()
    assert model.route_medians is not None
    return MetadataResponse(
        allowed={
            "airline": ALLOWED_AIRLINES,
            "city": ALLOWED_CITIES,
            "time": ALLOWED_TIMES,
            "stops": ALLOWED_STOPS,
            "class": list(CLASS_MAP.keys()),
        },
        defaults={
            "global_duration_median": model.route_medians.global_duration_median,
        },
    )


@app.get("/api/health")
def health():
    model = load_or_train_model()
    return {
        "status": "ok",
        "model_version": model.model_version,
        "has_pipeline": model.pipeline is not None,
    }


@app.get("/api/route-median")
def route_median(source_city: str, destination_city: str):
    model = load_or_train_model()
    assert model.route_medians is not None
    key = (source_city, destination_city)
    route_med = model.route_medians.route_to_duration_median.get(key)
    return {
        "source_city": source_city,
        "destination_city": destination_city,
        "route_median": route_med,
        "global_median": model.route_medians.global_duration_median,
    }


@app.post("/api/predict", response_model=PredictResponse)
def predict(payload: PredictRequest):
    try:
        data = payload.model_dump(by_alias=True)
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=str(e))

    # Normalize optional fields and apply defaults
    airline = data.get("airline") or "Unknown"
    departure_time = data.get("departure_time") or "Unknown"
    arrival_time = data.get("arrival_time") or "Unknown"

    # Map class and stops
    cabin_class = data["class"]
    days_left = int(data["days_left"])  # Already validated >=0
    stops = data["stops"]

    # Build feature row
    model = load_or_train_model()

    # Impute duration if missing
    duration_input = data.get("duration")
    duration, was_imputed, imputed_value = model.impute_duration(
        data["source_city"], data["destination_city"], duration_input
    )

    X = pd.DataFrame([
        {
            "source_city": data["source_city"],
            "destination_city": data["destination_city"],
            "class": 1 if cabin_class == "Business" else 0,
            "stops": {"zero": 0, "one": 1, "two_or_more": 2}[stops],
            "days_left": days_left,
            "duration": duration,
            "airline": airline,
            "departure_time": departure_time,
            "arrival_time": arrival_time,
        }
    ])

    pred, lower, upper = model.predict_with_uncertainty(X)
    contribs = model.local_contributions(X)

    assumptions = {}
    if was_imputed:
        assumptions["duration"] = {
            "value": duration,
            "imputed": True,
            "method": "route_median",
            "hint": "No duration provided; using typical median for this route.",
        }
    for cat_field, val, default in (
        ("airline", airline, "Unknown"),
        ("departure_time", departure_time, "Unknown"),
        ("arrival_time", arrival_time, "Unknown"),
    ):
        if val == default and (payload.model_dump().get(cat_field) in (None, "")):
            assumptions[cat_field] = {
                "value": val,
                "imputed": True,
                "method": "default_unknown",
            }

    response = PredictResponse(
        predicted_price=pred,
        lower_bound=max(lower, 0.0),
        upper_bound=max(upper, 0.0),
        top_contributors=contribs,
        assumptions_used=assumptions,
        echo=data,
    )

    # Append anonymized log
    try:
        logs_dir = Path(__file__).resolve().parents[1] / "logs"
        logs_dir.mkdir(parents=True, exist_ok=True)
        log_path = logs_dir / "predictions.csv"
        # sanitize echo, drop flight number
        echo = dict(data)
        echo.pop("flight", None)
        row = {
            "ts": datetime.utcnow().isoformat(),
            "predicted": response.predicted_price,
            "lower": response.lower_bound,
            "upper": response.upper_bound,
            **echo,
        }
        header_needed = not log_path.exists()
        import csv
        with open(log_path, "a", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(row.keys()))
            if header_needed:
                w.writeheader()
            w.writerow(row)
    except Exception:
        # best-effort logging; ignore failures
        pass

    return response
