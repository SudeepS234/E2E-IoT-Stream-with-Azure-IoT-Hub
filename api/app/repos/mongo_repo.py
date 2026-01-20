
from pymongo import MongoClient, ASCENDING
from typing import Dict, Any, List

class MongoRepo:
    def __init__(self, uri: str, db_name: str) -> None:
        self.client = MongoClient(uri)
        self.db = self.client[db_name]
        self.telemetry = self.db["telemetry"]
        self.devices = self.db["devices"]
        self.alerts = self.db["alerts"]

        # minimal index
        self.telemetry.create_index([("deviceId", ASCENDING), ("ts", ASCENDING)])

    def insert_telemetry(self, doc: Dict[str, Any]) -> None:
        self.telemetry.insert_one(doc)
        self.devices.update_one(
            {"_id": doc["deviceId"]},
            {"$setOnInsert": {"firstSeen": doc["ts"]}, "$set": {"lastSeen": doc["ts"]}},
            upsert=True,
        )

    def query_telemetry(self, device_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        cur = self.telemetry.find({"deviceId": device_id},{"_id": 0}).sort("ts", -1).limit(limit)
        return list(cur)[::-1]  # ascending order
