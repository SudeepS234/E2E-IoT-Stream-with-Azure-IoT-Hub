"""
Summary of Data Flow:
1) Start: call consumer.start() from main.py.

2) Connect: The client connects to Azure on port 443.

3) Receive: Azure sends a batch of messages.

4) Process: The script extracts the Device ID from the header, puts it in the JSON body.

5) Callback: The script gives the clean JSON to _on_telemetry function in main.py.

6) Checkpoint: The script tells Azure "I'm done with these messages."
"""
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
            transport_type=TransportType.AmqpOverWebsocket  # firewall friendly; specifies how the connection with IoT hub has to be made, StandardAMQP is blocked by corporate firewall hence amqpoverwebsocket is used which tunnels the message via HTTPS (443) so nothing gets blocked
        )
        self._task = None

    async def _handle_events(self, partition_context, events):
        for event in events:
            device_id = None
            try:
                # IoT Hub adds system properties including device id  
                sp = event.system_properties # when iot hub sends data to event hub it adds system properties automatically which includes the device id; then the next statement checks whether the device id is received to event hub as bytes or strings, if its bytes then has to be decoded to string for working with python, if its already string then its fine
                device_id = sp.get(b"iothub-connection-device-id", b"").decode() \
                            if isinstance(sp.get(b"iothub-connection-device-id"), (bytes, bytearray)) \
                            else sp.get("iothub-connection-device-id") # this 3 lines try to take the device_id from the AMQP header if it was sent by iot hub to event hub

                body = event.body_as_str(encoding="utf-8") # convert raw message body to string
                data = json.loads(body) # load the string as json for easy handling of the message
                if device_id:
                    data["deviceId"] = device_id # the device_id taken from the header is directly injected into the data dictionary. This ensures the downstream processor knows who sent the data without needing to look at headers.
                await self._on_telemetry(data) # the final step of ingestion where the received raw data from event hub is cleaned (from previous lines of code)
            except Exception as ex:
                print(f"[consumer] parse error: {ex} | device={device_id}")

        # optional: checkpoint occasionally to mark progress
        try:
            await partition_context.update_checkpoint() # updating azure that until this time i have received the messages so updating the checkpoint, else if the api script fails and runs again then azure will send all the old messages again from start which will cause duplication problems
        except Exception:
            pass

    async def _run(self):
        async with self._client:
            await self._client.receive_batch( # method to ask the client to start pulling the data from the stream
                on_event_batch=self._handle_events, # handler function for the received batch to specify what to do with the received data from event hub
                max_wait_time=5.0, # if not event happens then wait for max 5 seconds but makes sure loop stays active without closing connection
            )

    # start and stop are used for lifecycle management
    def start(self, loop: asyncio.AbstractEventLoop):
        self._task = loop.create_task(self._run()) # if self._run() is used directly then it will freeze the program and run it in the foreground making awaits and connections hard to handle so it is bounded inside asyncio loop object which makes it to run in the background and does not affect the program execution main task

    async def stop(self):
        if self._task:
            self._task.cancel() # shuts down the background task
            try:
                await self._task # wait for the task to finish clean up of itself
            except asyncio.CancelledError: # if the task is force cancelled then python raises this error
                pass
