
from typing import Optional, Dict

class AlertEngine:
    def __init__(self, temp_gt: Optional[float] = None) -> None:
        self.temp_gt = temp_gt

    def eval(self, telemetry: Dict) -> Optional[Dict]:
        t = telemetry.get("temperature")
        if self.temp_gt is not None and t is not None and t > self.temp_gt:
            return {
                "deviceId": telemetry["deviceId"],
                "ts": telemetry["ts"],
                "type": "threshold",
                "metric": "temperature",
                "value": t,
                "rule": f"temp_gt_{self.temp_gt}",
                "severity": "high",
                "state": "active",
            }
        return None
