
import json
import asyncio
from typing import Callable, Awaitable
from azure.eventhub.aio import EventHubConsumerClient
from azure.eventhub import TransportType

# event.system_properties keys like 'iothub-connection-device-id' contain the device id

class TelemetryConsumer:
    def __init__(
        self,
        eh_conn_str: str,
        consumer_group: str,
        on_telemetry: Callable[[dict], Awaitable[None]],
    ) -> None:
        self._conn_str = eh_conn_str
        self._group = consumer_group
        self._on_telemetry = on_telemetry
        self._client = EventHubConsumerClient.from_connection_string(
            conn_str=self._conn_str,
            consumer_group=self._group,
            transport_type=TransportType.AmqpOverWebsocket  # firewall-friendly (443)
        )
        self._task = None

    async def _handle_events(self, partition_context, events):
        for event in events:
            device_id = None
            try:
                # IoT Hub adds system properties including device id
                sp = event.system_properties
                device_id = sp.get(b"iothub-connection-device-id", b"").decode() \
                            if isinstance(sp.get(b"iothub-connection-device-id"), (bytes, bytearray)) \
                            else sp.get("iothub-connection-device-id")

                body = event.body_as_str(encoding="utf-8")
                data = json.loads(body)
                if device_id:
                    data["deviceId"] = device_id
                await self._on_telemetry(data)
            except Exception as ex:
                print(f"[consumer] parse error: {ex} | device={device_id}")

        # optional: checkpoint occasionally to mark progress
        try:
            await partition_context.update_checkpoint()
        except Exception:
            pass

    async def _run(self):
        async with self._client:
            await self._client.receive_batch(
                on_event_batch=self._handle_events,
                max_wait_time=5.0,
            )

    def start(self, loop: asyncio.AbstractEventLoop):
        self._task = loop.create_task(self._run())

    async def stop(self):
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
