"""
A performant and fault-tolerant WebSocket source for Quixstreams.
"""
# flake8: noqa: E501
import asyncio
import json
import logging
import time
from datetime import datetime
from typing import Callable, Dict, Optional, Union

import websocket
from quixstreams.sources.base.source import Source

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
        key_func (Optional[Callable[[dict], dict]]): Function to generate the key for the message.
        timestamp_func (Optional[Callable[[dict], int]]): Function to generate the timestamp for the message.
        headers_func (Optional[Callable[[dict], dict]]): Function to generate custom headers for each message.
        reconnect_delay (float): Delay (in seconds) before attempting reconnection.
        debug (bool): Whether to log detailed debug messages.

    Example Usage:
    ```python
    source = WebsocketSource(
        name="my_ws_source",
        ws_url="wss://ws-feed.example.com",
        subscribe_payload={"type": "subscribe", "channel": "example_channel"},
        key_func=lambda msg: {"id": msg.get("id")},
        timestamp_func=lambda msg: int(msg.get("timestamp", time.time() * 1000)),
        headers_func=lambda msg: {"X-Custom-Header": "value"},
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
        auth_payload: Optional[Dict] = None,
        subscribe_payload: Optional[Dict] = None,
        validator: Optional[Callable[[Dict], bool]] = None,
        transform: Optional[Callable[[Dict], Dict]] = None,
        key_func: Optional[Callable[[Dict], Dict]] = None,
        timestamp_func: Optional[Callable[[Dict], int]] = None,
        headers_func: Optional[Callable[[Dict], Dict]] = None,
        reconnect_delay: float = 5.0,
        debug: bool = False,
    ):
        super().__init__(name)
        self.ws_url = ws_url
        self.auth_payload = auth_payload
        self.subscribe_payload = subscribe_payload
        self.validator = validator
        self.transform = transform
        self.key_func = key_func
        self.timestamp_func = timestamp_func
        self.headers_func = headers_func
        self.reconnect_delay = reconnect_delay
        self.debug = debug
        self.ws = None
        self._msg_count = 0
        self._running = True

    def on_open(self, ws):
        """Callback when WebSocket connection is opened."""
        logger.info("WebSocket connection opened")
        if self.auth_payload:
            auth_msg = json.dumps(self.auth_payload, indent=2, sort_keys=True)
            logger.info(f"Sending authentication payload: {auth_msg}")
            ws.send(auth_msg)

        if self.subscribe_payload:
            subscribe_msg = json.dumps(self.subscribe_payload, indent=2, sort_keys=True)
            logger.info(f"Sending subscription payload: {subscribe_msg}")
            ws.send(subscribe_msg)

    def _process_message(self, data: Dict):
        """Processes a single message."""

        if self.debug:
            logger.debug(f"Message #{self._msg_count} Received!:\n {json.dumps(data, indent=2, sort_keys=True)}")

        if self.validator and not self.validator(data):
            logger.warning(f"Message failed validation:\n {json.dumps(data, indent=2, sort_keys=True)}")
            return

        key = self._generate_key(data)
        timestamp = self._generate_timestamp(data)
        headers = self._generate_headers(data)

        if self.debug:
            logger.debug("Transforming message...")
            logger.debug(f"Generated key: {key}")
            logger.debug(f"Generated timestamp: {timestamp}")
            logger.debug(f"Generated headers: {headers}")

        if self.transform:
            try:
                print(f"Transforming message: {data}")
                data = self.transform(data)
            except TypeError as e:
                logger.error(f"Error processing message: {e}", exc_info=True)
                return

        if self.debug:
            logger.debug(f"Transformed message: {json.dumps(data, indent=2, sort_keys=True)}")

        msg = self.serialize(
            key=key,
            value=data,
            headers=headers,
            timestamp_ms=timestamp,
        )

        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(f"Producing message: {json.dumps(msg, indent=2, sort_keys=True)}")

        self.produce(
            key=msg.key,
            value=msg.value,
            timestamp=msg.timestamp,
            headers=msg.headers,
        )

        if self.debug:
            logger.debug("Message produced successfully!")

    def on_message(self, ws, message):
        """Callback when a message is received."""
        self._msg_count += 1
        try:
            data = json.loads(message)
            print(json.dumps(data, indent=2))
            if self.debug:
                logger.debug(f"Received message: {data}")
            if isinstance(data, list):
                for msg in data:
                    self._process_message(msg)
            elif isinstance(data, dict):
                self._process_message(data)
        except Exception as e:
            logger.error(f"Error processing message: {e}", exc_info=True)
            ws.close()
            time.sleep(self.reconnect_delay)
            self._attempt_reconnect()

    def on_error(self, ws, error):
        """Callback when an error occurs."""
        logger.error(f"WebSocket error: {error}", exc_info=True)
        self.flush()
        self._attempt_reconnect()

    def on_close(self, ws, close_status_code, close_msg):
        """Callback when WebSocket connection is closed."""
        logger.info(f"WebSocket connection closed: {close_status_code}, {close_msg}")
        self.flush()
        self._attempt_reconnect()

    def _attempt_reconnect(self):
        """Attempts to reconnect to the WebSocket after a delay."""
        logger.info(f"Reconnecting in {self.reconnect_delay} seconds...")
        self._running = False
        time.sleep(self.reconnect_delay)
        self.run()

    def _generate_key(self, data: Dict) -> Optional[Dict]:
        """Generates the key for the message using the provided key function."""
        if self.debug:
            logger.debug(f"Generating key for message: {data}")
        if not self.key_func:
            return None
        try:
            return self.key_func(data)
        except Exception as e:
            logger.error(f"Error generating key: {e}", exc_info=True)
            return None

    def _generate_timestamp(self, data: Dict) -> int:
        """Generates the timestamp for the message using the provided timestamp function."""
        if self.debug:
            logger.debug(f"Generating timestamp for message: {data}")
        try:
            if self.timestamp_func:
                return self.timestamp_func(data)
            return int(datetime.utcnow().timestamp() * 1000)  # Current timestamp in milliseconds
        except Exception as e:
            logger.error(f"Error generating timestamp: {e}", exc_info=True)
            return int(datetime.utcnow().timestamp() * 1000)

    def _generate_headers(self, data: Dict) -> Dict[str, str]:
        """Generates custom headers for the message using the provided headers function."""
        if self.debug:
            logger.debug(f"Generating headers for message: {data}")
        if not self.headers_func:
            return {}
        try:
            return self.headers_func(data)
        except Exception as e:
            logger.error(f"Error generating headers: {e}", exc_info=True)
            return {}

    def run(self):
        """Starts the WebSocket connection."""
        while self._running:
            try:
                logger.info(f"Connecting to WebSocket at {self.ws_url}")
                self.ws = websocket.WebSocketApp(
                    self.ws_url,
                    on_open=self.on_open,
                    on_message=self.on_message,
                    on_error=self.on_error,
                    on_close=self.on_close,
                )
                self.ws.run_forever()
            except Exception as e:
                logger.error(f"WebSocket connection error: {e}", exc_info=True)
                self._attempt_reconnect()

    def stop(self):
        """Stops the WebSocket connection."""
        logger.info("Stopping WebSocket source...")
        self._running = False
        if self.ws:
            self.ws.close()


__all__ = ["WebsocketSource"]
