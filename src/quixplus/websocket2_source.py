import asyncio
from datetime import datetime
import json
import logging
import threading
from typing import Callable, Dict, Optional, Union

from quixstreams.sources.base.source import Source
import websocket


logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


class WebsocketSource(Source):
    """
    A performant and fault-tolerant WebSocket source for Quixstreams.

    Attributes:
        ws_url (str): The complete WebSocket URL to connect to.
        auth_payload (Optional[dict]): Authentication payload sent upon connection.
        subscribe_payload (Optional[dict]): Subscription payload sent upon connection.
        validator (Optional[Callable[[dict], bool]]): Function to validate incoming messages.
        transform (Optional[Callable[[dict], dict]]): Function to transform incoming messages.
        key_func (Optional[Callable[['WebsocketSource', dict], dict]]): Function to generate the key for the message.
        timestamp_func (Optional[Callable[['WebsocketSource', dict], int]]): Function to generate the timestamp for the message.
        custom_headers_func (Optional[Callable[['WebsocketSource', dict], dict]]): Function to generate custom headers for each message.
        reconnect_delay (float): Delay (in seconds) before attempting reconnection.
        debug (bool): Whether to log detailed debug messages.

    Example Usage:
    ```python
    source = WebsocketSource(
        name="my_ws_source",
        ws_url="wss://ws-feed.example.com",
        subscribe_payload={"type": "subscribe", "channel": "example_channel"},
        key_func=lambda self, msg: {"id": msg.get("id")},
        timestamp_func=lambda self, msg: int(msg.get("timestamp", time.time() * 1000)),
        custom_headers_func=lambda self, msg: {"X-Custom-Header": "value"},
        debug=True
    )
    app.add_source(source, topic)
    app.run()
    ```
    """

    def __init__(
        self,
        name: str,
        ws_url: str,
        auth_payload: Optional[Dict]=None,
        subscribe_payload: Optional[Dict]=None,
        validator: Optional[Callable[[Dict], bool]]=None,
        transform: Optional[Callable[[Dict], Dict]]=None,
        key_func: Optional[Callable[['WebsocketSource', Dict], Dict]]=None,
        timestamp_func: Optional[Callable[['WebsocketSource', Dict], int]]=None,
        custom_headers_func: Optional[Callable[['WebsocketSource', Dict], Dict]]=None,
        reconnect_delay: float=5.0,
        debug: bool=False,
    ):
        super().__init__(name)
        self.ws_url = ws_url
        self.auth_payload = auth_payload
        self.subscribe_payload = subscribe_payload
        self.validator = validator
        self.transform = transform
        self.key_func = key_func
        self.timestamp_func = timestamp_func
        self.custom_headers_func = custom_headers_func
        self.reconnect_delay = reconnect_delay
        self.debug = debug
        self.running = False
        self.ws = None

    def on_open(self, ws):
        """Callback when WebSocket connection is opened."""
        logger.info("WebSocket connection opened")
        if self.auth_payload:
            ws.send(json.dumps(self.auth_payload))
            logger.info("Sent authentication payload")

        if self.subscribe_payload:
            ws.send(json.dumps(self.subscribe_payload))
            logger.info("Sent subscription payload")

    def on_message(self, ws, message):
        """Callback when a message is received."""
        try:
            data = json.loads(message)
            if self.debug:
                logger.debug(f"Received message: {data}")

            if self.validator and not self.validator(data):
                logger.warning(f"Message failed validation: {data}")
                return

            if self.transform:
                data = self.transform(data)

            key = self._generate_key(data)
            timestamp = self._generate_timestamp(data)
            headers = self._generate_headers(data)

            msg = self.serialize(
                key=key,
                value=data,
                timestamp=timestamp,
                headers=headers,
            )
            self.produce(
                key=msg.key,
                value=msg.value,
                timestamp=msg.timestamp,
                headers=msg.headers,
            )
        except Exception as e:
            logger.error(f"Error processing message: {e}")

    def on_error(self, ws, error):
        """Callback when an error occurs."""
        logger.error(f"WebSocket error: {error}")
        self._attempt_reconnect()

    def on_close(self, ws, close_status_code, close_msg):
        """Callback when WebSocket connection is closed."""
        logger.info(f"WebSocket connection closed: {close_status_code}, {close_msg}")
        self._attempt_reconnect()

    def _attempt_reconnect(self):
        """Attempts to reconnect to the WebSocket after a delay."""
        logger.info(f"Reconnecting in {self.reconnect_delay} seconds...")
        self.running = False
        asyncio.sleep(self.reconnect_delay)
        self.run()

    def _generate_key(self, data: Dict) -> Optional[Dict]:
        """Generates the key for the message using the provided key function."""
        if not self.key_func:
            return None
        try:
            return self.key_func(self, data)
        except Exception as e:
            logger.error(f"Error generating key: {e}")
            return None

    def _generate_timestamp(self, data: Dict) -> int:
        """Generates the timestamp for the message using the provided timestamp function."""
        try:
            if self.timestamp_func:
                return self.timestamp_func(self, data)
            return int(datetime.utcnow().timestamp() * 1000)  # Current timestamp in milliseconds
        except Exception as e:
            logger.error(f"Error generating timestamp: {e}")
            return int(datetime.utcnow().timestamp() * 1000)

    def _generate_headers(self, data: Dict) -> Dict[str, str]:
        """Generates custom headers for the message using the provided headers function."""
        if not self.custom_headers_func:
            return {}
        try:
            return self.custom_headers_func(self, data)
        except Exception as e:
            logger.error(f"Error generating headers: {e}")
            return {}

    def run(self):
        """Starts the WebSocket connection."""
        self.running = True
        while self.running:
            try:
                logger.info(f"Connecting to WebSocket at {self.ws_url}")
                self.ws = websocket.WebSocketApp(
                    self.ws_url,
                    on_open=self.on_open,
                    on_message=self.on_message,
                    on_error=self.on_error,
                    on_close=self.on_close,
                )
                wst = threading.Thread(target=self.ws.run_forever)
                wst.daemon = True
                wst.start()
                wst.join()  # Wait for the thread to terminate
            except Exception as e:
                logger.error(f"WebSocket connection error: {e}")
                self._attempt_reconnect()

    def stop(self):
        """Stops the WebSocket connection."""
        logger.info("Stopping WebSocket source...")
        self.running = False
        if self.ws:
            self.ws.close()


__all__ = ["WebsocketSource"]
