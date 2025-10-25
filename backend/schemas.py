from __future__ import annotations
from typing import Optional, Literal, Dict, Any, List
from pydantic import BaseModel, Field, field_validator

City = Literal["Delhi", "Mumbai", "Bangalore", "Kolkata", "Hyderabad", "Chennai"]
TimeBand = Literal["Early_Morning", "Morning", "Afternoon", "Evening", "Night", "Late_Night", "Unknown"]
Stops = Literal["zero", "one", "two_or_more"]
CabinClass = Literal["Economy", "Business"]
Airline = Literal["Vistara", "Air_India", "Indigo", "GO_FIRST", "AirAsia", "SpiceJet", "Unknown"]


class PredictRequest(BaseModel):
    source_city: City
    destination_city: City
    cabin_class: CabinClass = Field(alias="class")
    stops: Stops
    days_left: int = Field(ge=0)

    duration: Optional[float] = Field(default=None, gt=0)
    airline: Optional[Airline] = None
    departure_time: Optional[TimeBand] = None
    arrival_time: Optional[TimeBand] = None

    flight: Optional[str] = None  # Ignored by model, accepted for UX completeness

    @field_validator("destination_city")
    @classmethod
    def _not_same_city(cls, v: City, info):
        data = info.data
        sc = data.get("source_city")
        if sc and v == sc:
            raise ValueError("Source and destination can’t be the same.")
        return v


class Contributor(BaseModel):
    feature: str
    contribution: float
    direction: Literal["+", "-"]


class PredictResponse(BaseModel):
    predicted_price: float
    lower_bound: float
    upper_bound: float
    top_contributors: List[Contributor]
    assumptions_used: Dict[str, Any]
    echo: Dict[str, Any]


class MetadataResponse(BaseModel):
    allowed: Dict[str, List[str]]
    defaults: Dict[str, Any]
