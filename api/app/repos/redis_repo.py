
import json
import redis

class RedisRepo:
    def __init__(self, url: str) -> None:
        self.client = redis.Redis.from_url(url)

    def set_latest(self, device_id: str, doc: dict) -> None:
        key = f"device:{device_id}:latest"
        self.client.set(key, json.dumps(doc), ex=24*3600)

    def get_latest(self, device_id: str):
        key = f"device:{device_id}:latest"
        raw = self.client.get(key)
        return json.loads(raw) if raw else None

    def publish_alert(self, alert: dict) -> None:
        self.client.publish("alerts:stream", json.dumps(alert))
