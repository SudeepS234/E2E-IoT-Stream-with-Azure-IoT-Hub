from pydantic import BaseModel, Field
from typing import Optional, Dict

class TelemetryIn(BaseModel):
    ts: str
    temperature: float
    humidity: float
    battery: int
    status: str
    props: Optional[Dict[str, str]] = Field(default_factory=dict)

class TelemetryDoc(TelemetryIn):
    deviceId: str
