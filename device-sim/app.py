
import base64
import hashlib
import hmac
import json
import os
import random
import ssl
import time
import urllib.parse
from datetime import datetime

import paho.mqtt.client as mqtt
from dotenv import load_dotenv

# -----------------------------
# Load environment (optional)
# -----------------------------
load_dotenv()

# -----------------------------
# CONFIG: fill these or use .env
# -----------------------------
IOTHUB_HOST = os.getenv("IOTHUB_HOST")  # HostName (no scheme)
DEVICE_ID = os.getenv("DEVICE_ID")
DEVICE_KEY = os.getenv("DEVICE_KEY")  # Base64 symmetric key
API_VERSION = "2021-04-12"  # required in MQTT username for IoT Hub
USE_WEBSOCKETS = os.getenv("USE_WEBSOCKETS", True)
SEND_INTERVAL_SECONDS = int(os.getenv("SEND_INTERVAL_SECONDS", "5"))
SAS_TTL_SECONDS = int(os.getenv("SAS_TTL_SECONDS", "3600"))

# -----------------------------
# Helpers
# -----------------------------
def build_sas_token(host: str, device_id: str, key_b64: str, ttl_seconds: int = 3600) -> str:
    """
    Build a SAS token for device-scoped auth:
      sr = {host}/devices/{deviceId}  (URL-encoded in the token)
      sig = HMAC-SHA256 over "{sr}\n{expiry}"
      se = unix epoch expiry
    """
    expiry = int(time.time()) + ttl_seconds
    resource_uri = f"{host}/devices/{device_id}"
    encoded_resource = urllib.parse.quote(resource_uri, safe="")
    to_sign = f"{encoded_resource}\n{expiry}".encode("utf-8")

    key = base64.b64decode(key_b64)
    signature = hmac.new(key, to_sign, hashlib.sha256).digest()
    signature_b64 = urllib.parse.quote(base64.b64encode(signature))

    return f"SharedAccessSignature sr={encoded_resource}&sig={signature_b64}&se={expiry}"


def build_payload() -> dict:
    """
    Generate telemetry with LOCAL time (your preference).
    """
    now_local = datetime.now().astimezone().isoformat()
    return {
        "ts": now_local,
        "temperature": round(24 + random.uniform(-2, 8), 2),
        "humidity": round(50 + random.uniform(-5, 12), 2),
        "battery": max(0, min(100, int(90 + random.uniform(-12, 0)))),
        "status": random.choice(["OK", "OK", "OK", "WARN"]),  # mostly OK
        "props": {"fw": "1.0.0", "site": "lab-A"},
    }


def safe_publish(client: mqtt.Client, topic: str, payload: str, qos: int = 1, retries: int = 5) -> bool:
    """
    Publish with simple reconnect-aware retries.
    When the client is reconnecting, publish() will often return rc=4 (MQTT_ERR_NO_CONN).
    """
    for attempt in range(retries):
        if client.is_connected():
            r = client.publish(topic, payload=payload, qos=qos)
            if r.rc == mqtt.MQTT_ERR_SUCCESS:
                return True
        # allow time for automatic reconnect to happen
        time.sleep(1 + attempt)  # linear backoff
    print("[warn] publish failed after retries")
    return False


# -----------------------------
# MQTT callbacks (Callback API v2)
# -----------------------------
def on_connect(client: mqtt.Client, userdata, flags, reason_code, properties=None):
    print(f"[connect] reason_code={reason_code}")  # 0 means success
    if reason_code == 0:
        # Subscribe to C2D messages (optional; requires Standard tier to actually send)
        topic_filter = f"devices/{DEVICE_ID}/messages/devicebound/#"
        client.subscribe(topic_filter, qos=1)
        print(f"[c2d] subscribed: {topic_filter}")
    else:
        print("[error] not connected. Check SAS token, username, clock skew, or ports.")


def on_disconnect(client: mqtt.Client, userdata, reason_code, properties=None):
    print(f"[disconnect] reason_code={reason_code} (0 means clean; non-zero unexpected)")


def on_message(client: mqtt.Client, userdata, msg):
    # C2D messages (if any) arrive here
    try:
        body = msg.payload.decode("utf-8", errors="ignore")
    except Exception:
        body = "<binary>"
    print(f"[c2d] topic={msg.topic} payload={body}")


def on_log(client: mqtt.Client, userdata, level, buf):
    # Verbose Paho logs (useful during troubleshooting)
    print("[paho]", buf)


# -----------------------------
# Main
# -----------------------------
def main():
    if not DEVICE_KEY or DEVICE_KEY.startswith("<"):
        raise RuntimeError("DEVICE_KEY is not set. Put it in .env or directly in the script.")

    sas = build_sas_token(IOTHUB_HOST, DEVICE_ID, DEVICE_KEY, ttl_seconds=SAS_TTL_SECONDS)

    username = f"{IOTHUB_HOST}/{DEVICE_ID}/?api-version={API_VERSION}"
    client_id = DEVICE_ID

    transport = "websockets" if USE_WEBSOCKETS else "tcp"
    port = 443 if USE_WEBSOCKETS else 8883

    # Create client with Callback API v2 to avoid deprecation warnings
    client = mqtt.Client(
        client_id=client_id,
        transport=transport,
        protocol=mqtt.MQTTv311,
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
    )
    client.username_pw_set(username=username, password=sas)

    # TLS required by IoT Hub
    client.tls_set(tls_version=ssl.PROTOCOL_TLSv1_2)
    client.tls_insecure_set(False)

    # Attach callbacks
    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    client.on_message = on_message
    client.on_log = on_log  # comment out to reduce verbosity

    # Optionally tune reconnect backoff
    client.reconnect_delay_set(min_delay=1, max_delay=8)

    print(f"[info] connecting to {IOTHUB_HOST}:{port}  transport={transport}")
    print(f"[info] username='{username}'")
    client.connect(IOTHUB_HOST, port=port, keepalive=60)
    client.loop_start()

    d2c_topic = f"devices/{DEVICE_ID}/messages/events/"

    try:
        while True:
            payload_dict = build_payload()
            payload = json.dumps(payload_dict, separators=(",", ":"))
            ok = safe_publish(client, d2c_topic, payload, qos=1, retries=5)
            rc_txt = "ok" if ok else "fail"
            print(f"[d2c:{rc_txt}] topic={d2c_topic} payload={payload}")
            time.sleep(SEND_INTERVAL_SECONDS)
    except KeyboardInterrupt:
        print("Exiting...")
    finally:
        client.loop_stop()
        client.disconnect()


if __name__ == "__main__":
    main()
