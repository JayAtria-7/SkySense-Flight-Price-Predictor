from __future__ import annotations
from pathlib import Path
from dataclasses import dataclass
from typing import Dict, Tuple, Any, List

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, FunctionTransformer
from sklearn.impute import SimpleImputer
from sklearn.ensemble import RandomForestRegressor
import joblib
import time


ALLOWED_AIRLINES = [
    "Vistara", "Air_India", "Indigo", "GO_FIRST", "AirAsia", "SpiceJet", "Unknown"
]
ALLOWED_CITIES = ["Delhi", "Mumbai", "Bangalore", "Kolkata", "Hyderabad", "Chennai"]
ALLOWED_TIMES = [
    "Early_Morning", "Morning", "Afternoon", "Evening", "Night", "Late_Night", "Unknown"
]
ALLOWED_STOPS = ["zero", "one", "two_or_more"]
ALLOWED_CLASS = ["Economy", "Business"]

STOPS_MAP = {"zero": 0, "one": 1, "two_or_more": 2}
CLASS_MAP = {"Economy": 0, "Business": 1}


@dataclass
class RouteMedians:
    route_to_duration_median: Dict[Tuple[str, str], float]
    global_duration_median: float


class FlightPriceModel:
    def __init__(self):
        self.pipeline: Pipeline | None = None
        self.route_medians: RouteMedians | None = None
        self.feature_names_out_: List[str] | None = None
        self.model_path: Path | None = None
        self.model_version: str | None = None

    def _load_data(self, data_path: Path) -> pd.DataFrame:
        df = pd.read_csv(data_path)
        return df

    @staticmethod
    def _prepare_training_frame(df: pd.DataFrame) -> pd.DataFrame:
        # Drop irrelevant
        df = df.drop(columns=[col for col in ["Unnamed: 0", "flight"] if col in df.columns])

        # Ensure categorical optional values have 'Unknown' where missing
        for col, allowed in (
            ("airline", ALLOWED_AIRLINES),
            ("source_city", ALLOWED_CITIES),
            ("departure_time", ALLOWED_TIMES),
            ("arrival_time", ALLOWED_TIMES),
            ("destination_city", ALLOWED_CITIES),
        ):
            if col in df.columns:
                df[col] = df[col].astype(str)
                df[col] = df[col].where(df[col].isin(allowed), "Unknown")

        # Normalize stops/class per spec
        if "stops" in df.columns:
            df["stops"] = df["stops"].map(STOPS_MAP).astype(int)
        if "class" in df.columns:
            # Business -> 1, Economy -> 0
            df["class"] = df["class"].map(CLASS_MAP).astype(int)

        # Basic sanity for numeric
        if "days_left" in df.columns:
            df["days_left"] = pd.to_numeric(df["days_left"], errors="coerce").fillna(0).clip(lower=0).astype(int)
        if "duration" in df.columns:
            df["duration"] = pd.to_numeric(df["duration"], errors="coerce")

        return df

    def _build_route_medians(self, df: pd.DataFrame) -> RouteMedians:
        # Build medians by (source_city, destination_city)
        if {"source_city", "destination_city", "duration"}.issubset(df.columns):
            route_group = (
                df.dropna(subset=["duration"]).groupby(["source_city", "destination_city"])  # type: ignore[arg-type]
            )["duration"].median()
            route_to_duration = {k: float(v) for k, v in route_group.to_dict().items()}
            global_med = float(df["duration"].median()) if not df["duration"].isna().all() else 2.0
        else:
            route_to_duration = {}
            global_med = 2.0
        return RouteMedians(route_to_duration, global_med)

    def _make_preprocessor(self) -> ColumnTransformer:
        numeric_features = ["duration", "days_left", "stops", "class"]
        cat_features = [
            "airline", "source_city", "departure_time", "arrival_time", "destination_city"
        ]

        numeric_transformer = Pipeline(steps=[
            ("imputer", SimpleImputer(strategy="median")),
        ])

        cat_transformer = Pipeline(steps=[
            ("imputer", SimpleImputer(strategy="most_frequent")),
            ("ohe", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
        ])

        preprocessor = ColumnTransformer(
            transformers=[
                ("num", numeric_transformer, numeric_features),
                ("cat", cat_transformer, cat_features),
            ], remainder="drop"
        )
        return preprocessor

    def train_or_load(self, data_path: Path) -> None:
        # Decide whether to load existing model
        self.model_path = data_path.parent / "backend" / "model.joblib"
        csv_mtime = data_path.stat().st_mtime if data_path.exists() else 0
        model_mtime = self.model_path.stat().st_mtime if self.model_path.exists() else 0

        if self.model_path.exists() and model_mtime >= csv_mtime:
            loaded = joblib.load(self.model_path)
            self.pipeline = loaded["pipeline"]
            self.route_medians = loaded["route_medians"]
            self.feature_names_out_ = loaded["feature_names_out"]
            self.model_version = loaded.get("model_version", f"loaded-{int(model_mtime)}")
            return

        # Train fresh
        df_raw = self._load_data(data_path)
        df = self._prepare_training_frame(df_raw.copy())
        self.route_medians = self._build_route_medians(df)

        y = df["price"].astype(float)
        X = df.drop(columns=["price"])  # flight already dropped

        preprocessor = self._make_preprocessor()
        model = RandomForestRegressor(n_jobs=-1, random_state=42)
        self.pipeline = Pipeline(steps=[("preprocessor", preprocessor), ("model", model)])
        self.pipeline.fit(X, y)

        # Cache feature names
        ohe = self.pipeline.named_steps["preprocessor"].named_transformers_["cat"].named_steps["ohe"]
        num_names = ["duration", "days_left", "stops", "class"]
        cat_names = list(ohe.get_feature_names_out([
            "airline", "source_city", "departure_time", "arrival_time", "destination_city"
        ]))
        self.feature_names_out_ = [*num_names, *cat_names]
        self.model_version = f"rf-{int(time.time())}"

        # Persist
        self.model_path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump({
            "pipeline": self.pipeline,
            "route_medians": self.route_medians,
            "feature_names_out": self.feature_names_out_,
            "model_version": self.model_version,
        }, self.model_path)

    # --- Inference helpers ---
    def impute_duration(self, source_city: str, destination_city: str, duration: float | None) -> Tuple[float, bool, float]:
        if duration is not None and duration > 0:
            return float(duration), False, 0.0
        assert self.route_medians is not None
        key = (source_city, destination_city)
        if key in self.route_medians.route_to_duration_median:
            imputed = self.route_medians.route_to_duration_median[key]
        else:
            imputed = self.route_medians.global_duration_median
        return float(imputed), True, float(imputed)

    def predict_with_uncertainty(self, features: pd.DataFrame) -> Tuple[float, float, float]:
        assert self.pipeline is not None
        model: RandomForestRegressor = self.pipeline.named_steps["model"]
        pred = float(self.pipeline.predict(features)[0])
        # Estimate uncertainty from per-tree predictions
        trees = np.array([est.predict(self.pipeline.named_steps["preprocessor"].transform(features))[0] for est in model.estimators_])
        std = float(np.std(trees))
        lower = pred - 1.96 * std
        upper = pred + 1.96 * std
        return pred, lower, upper

    def local_contributions(self, instance: pd.DataFrame) -> List[Dict[str, Any]]:
        """
        Approximate top contributors by comparing prediction to a baseline where
        optional categorical fields are set to 'Unknown' and numeric fields to medians.
        Compute deltas by toggling one feature group at a time.
        """
        assert self.pipeline is not None
        # Build baseline
        base = instance.copy()
        # Required fields preserved; optional to Unknown
        for col in ["airline", "departure_time", "arrival_time"]:
            if col in base.columns:
                base[col] = "Unknown"
        # Numeric defaults
        if "duration" in base.columns:
            # Use global median for contributions baseline
            assert self.route_medians is not None
            base["duration"] = self.route_medians.global_duration_median

        base_pred, _, _ = self.predict_with_uncertainty(base)
        curr_pred, _, _ = self.predict_with_uncertainty(instance)

        groups = [
            ("class", ["class"]),
            ("stops", ["stops"]),
            ("days_left", ["days_left"]),
            ("duration", ["duration"]),
            ("airline", ["airline"]),
            ("source_city", ["source_city"]),
            ("departure_time", ["departure_time"]),
            ("arrival_time", ["arrival_time"]),
            ("destination_city", ["destination_city"]),
        ]

        contribs: List[Dict[str, Any]] = []
        for name, cols in groups:
            toggled = base.copy()
            for c in cols:
                toggled[c] = instance[c]
            pred, _, _ = self.predict_with_uncertainty(toggled)
            delta = pred - base_pred
            contribs.append({
                "feature": name,
                "contribution": abs(float(delta)),
                "direction": "+" if delta >= 0 else "-",
            })
        contribs.sort(key=lambda x: x["contribution"], reverse=True)
        return contribs[:5]


MODEL_SINGLETON = FlightPriceModel()


def load_or_train_model() -> FlightPriceModel:
    if MODEL_SINGLETON.pipeline is None:
        data_path = Path(__file__).resolve().parents[1] / "Clean_Dataset.csv"
        MODEL_SINGLETON.train_or_load(data_path)
    return MODEL_SINGLETON
