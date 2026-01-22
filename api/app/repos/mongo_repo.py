
from pymongo import MongoClient, ASCENDING, DESCENDING
from typing import Dict, Any, List

class MongoRepo:
    def __init__(self, uri: str, db_name: str) -> None:
        self.client = MongoClient(uri)
        self.db = self.client[db_name]
        self.telemetry = self.db["telemetry"]
        self.devices = self.db["devices"]
        self.alerts = self.db["alerts"]

        # minimal index
        self.telemetry.create_index([("deviceId", ASCENDING), ("ts", DESCENDING)])

    def insert_telemetry(self, doc: Dict[str, Any]) -> None:
        self.telemetry.insert_one(doc)
        self.devices.update_one(
            {"_id": doc["deviceId"]}, #Find the device with the deviceId to update it
            {"$setOnInsert": {"firstSeen": doc["ts"]}, "$set": {"lastSeen": doc["ts"]}}, # parameters written here are functions starting with $ that perform specific actions; $setOnInsert runs only once when a new deviceId is created/enters first, so when the telemetry of a new deviceId comes in the firstseen timestamp for that is set and it will never change again; $set runs everytime so it will always store the latest timestamp received
            upsert=True, # updateNinsert - if the record with the deviceId is found then update else create a new record (fail proof) edge-case is when the first record is made for a particular device whose device id is not present in mongodb
        )

    def query_telemetry(self, device_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        cur = self.telemetry.find({"deviceId": device_id},{"_id": 0}).sort("ts", -1).limit(limit) 
        # syntax of .find({Query}, {projection}) where Query is like SQL WHERE condition so filter rows based on the {Query} rules then projection means the details to exclude from the data returned, in the sense of mongodb it always stores a _id property for every record created (it is a long arbitraty string) which is not required for us hence in this parameter we set "_id" as 0 which means false so that the _id is skipped and rest all items(columns) in the records are returned 
        return list(cur)
