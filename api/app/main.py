
import os
import asyncio
from typing import List, Dict
from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query
from fastapi.responses import JSONResponse

from .ws_manager import WSManager
from .models import TelemetryDoc
from .repos.mongo_repo import MongoRepo
from .repos.redis_repo import RedisRepo
from .alerts import AlertEngine
from .consumer import TelemetryConsumer

load_dotenv()

app = FastAPI(title="IoT Telemetry Ingestion & Live Dashboard")

# --- env
EH_CONN = os.getenv("EH_COMPAT_CONN_STR") or ""
EH_GROUP = os.getenv("EH_CONSUMER_GROUP", "$Default")  # but prefer a dedicated group
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB = os.getenv("MONGO_DB", "iot_demo")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
TEMP_GT = float(os.getenv("ALERT_TEMP_GT", "80"))

# --- deps
ws_manager = WSManager()
mongo = MongoRepo(MONGO_URI, MONGO_DB)
redis_repo = RedisRepo(REDIS_URL)
alerts = AlertEngine(temp_gt=TEMP_GT)

# The consumer is created on startup to read from built-in endpoint
consumer: TelemetryConsumer | None = None

# --- telemetry handler called by consumer
async def _on_telemetry(doc: Dict):
    # validate minimal schema via Pydantic
    telemetry = TelemetryDoc(**doc)
    # persist
    mongo.insert_telemetry(telemetry.model_dump())
    # update latest cache
    redis_repo.set_latest(telemetry.deviceId, telemetry.model_dump())
    # alerts
    alert = alerts.eval(telemetry.model_dump())
    if alert:
        mongo.alerts.insert_one(alert)
        redis_repo.publish_alert(alert)
        # also broadcast the alert
        await ws_manager.broadcast_json({"type": "alert", "data": alert})
    # broadcast live telemetry to dashboard
    await ws_manager.broadcast_json({"type": "telemetry", "data": telemetry.model_dump()})

# --- startup/shutdown
@app.on_event("startup")
async def on_startup():
    global consumer
    if not EH_CONN:
        raise RuntimeError("EH_COMPAT_CONN_STR is not set in environment.")
    consumer = TelemetryConsumer(EH_CONN, EH_GROUP, _on_telemetry)
    loop = asyncio.get_event_loop()
    consumer.start(loop)

@app.on_event("shutdown")
async def on_shutdown():
    global consumer
    if consumer:
        await consumer.stop()

# --- REST APIs ---
@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/devices", response_model=List[Dict])
def list_devices():
    # read device ids from Mongo devices collection for demo
    ids = [d["_id"] for d in mongo.devices.find({}, {"_id": 1})]
    out = []
    for did in ids:
        latest = redis_repo.get_latest(did)
        out.append({"deviceId": did, "latest": latest})
    return out

@app.get("/telemetry/{device_id}", response_model=List[Dict])
def get_telemetry(device_id: str, limit: int = Query(100, le=1000)):
    return mongo.query_telemetry(device_id, limit=limit)

# --- WebSockets for live UI ---
@app.websocket("/ws/telemetry")
async def ws_telemetry(ws: WebSocket):
    await ws_manager.connect(ws)
    try:
        while True:
            # We don't expect messages from client for now; just keep alive
            await ws.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(ws)
