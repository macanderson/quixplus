"""
A source for Quixstreams that reads data from a WebSocket server using Tornado.
"""
# flake8: noqa: E501
import json
import logging
import time
from typing import Any, Callable, Dict, List, Optional

from dotenv import load_dotenv
from quixstreams.sources.base.source import Source
from websocket import create_connection

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

load_dotenv()


class TornadoWebsocketSource(Source):
    """
    A source for Quixstreams that reads data from a WebSocket server using Tornado.

    Attributes:
        name (str): The name of the source.
        url (str): The WebSocket URL to connect to.
        subscription_payloads (Optional[List[Dict]]): List of payloads to send for subscribing to channels.
        auth_payload (Optional[Dict]): Authentication payload to send upon connection.
        validator_func (Callable[[Dict], bool]): Function to validate incoming messages.
        value_func (Callable[[Dict], Dict]]): Function to transform incoming messages.
        key_func (Optional[Callable[[Dict], Dict]]): Function to generate the key for the message.
        headers_func (Optional[Callable[[Dict], Dict]]): Function to generate custom headers for each message.
        timestamp_func (Optional[Callable[[Dict], int]]): Function to generate the timestamp for the message.
        reconnect_delay (float): Delay (in seconds) before attempting reconnection.
        shutdown_timeout (float): Time to wait for graceful shutdown.
        debug (bool): Whether to log detailed debug messages.
    Example Usage:
        ```python
        source = TornadoWebsocketSource(
            name="my_ws_source",
            url="wss://ws-feed.example.com",
            subscription_payloads=[{"type": "subscribe", "channel": "example_channel"}],
            auth_payload={"token": "example_token"},
            validator_func=lambda msg: "type" in msg and msg["type"] == "message",
            value_func=lambda msg: {"data": msg["data"]},
            key_func=lambda msg: {"id": msg.get("id")},
            headers_func=lambda msg: {"X-Custom-Header": "value"},
            timestamp_func=lambda msg: int(msg.get("timestamp", time.time() * 1000)),
            reconnect_delay=5.0,
            shutdown_timeout=10.0,
            debug=True
        )
        app.add_source(source, topic)
        app.run()
        ```
    """
    def __init__(
        self,
        name: str,
        url: str,
        subscription_payloads: Optional[List[Dict]] = None,
        auth_payload: Optional[Dict] = None,
        validator_func: Callable[[Dict], bool] = lambda x: True,
        value_func: Callable[[Dict], Dict] = lambda x: x,
        key_func: Optional[Callable[[Dict], Dict]] = None,
        headers_func: Optional[Callable[[Dict], Dict]] = None,
        timestamp_func: Optional[Callable[[Dict], int]] = None,
        reconnect_delay: float = 5.0,
        shutdown_timeout: float = 10.0,
        debug: bool = False,
    ):
        """
        Initialize the TornadoWebsocketSource.
        """
        super().__init__(name, shutdown_timeout)
        self.url = url
        self.subscription_payloads = subscription_payloads
        self.auth_payload = auth_payload
        self.validator_func = validator_func
        self.value_func = value_func
        self.key_func = key_func
        self.headers_func = headers_func
        self.timestamp_func = timestamp_func
        self.reconnect_delay = reconnect_delay
        self.shutdown_timeout = shutdown_timeout
        self.debug = debug
        if self.debug:
            logger.setLevel(logging.DEBUG)

    def run(self):
        """
        Connect to the WebSocket server and read messages.
        """
        while self._running:
            try:
                logger.info("Connecting to WebSocket...")
                ws = create_connection(self.url)
                logger.info("Connected to WebSocket")

                # Send authentication payload if available
                if self.auth_payload:
                    ws.send(json.dumps(self.auth_payload))
                    logger.debug(f"Sent auth payload: {self.auth_payload}")

                # Send subscription payloads if available
                if self.subscription_payloads:
                    for payload in self.subscription_payloads:
                        ws.send(json.dumps(payload))
                        logger.debug(f"Sent subscription payload: {payload}")

                while self._running:
                    message = ws.recv()
                    if not message:
                        logger.info("No message received, the connection is closed. Attempting to reconnect...")
                        break
                    logger.debug(f"Received message: {message}")
                    if self.validator_func(json.loads(message)):
                        self.produce(json.loads(message))
                    else:
                        logger.warning(f"Message validation failed: {message}")
            except Exception as e:
                logger.error(f"Error in run: {e}", exc_info=True)
                self.on_error(e)
            finally:
                try:
                    if ws:
                        ws.close()
                        logger.info("WebSocket connection closed.")
                except Exception as close_error:
                    logger.error(f"Error closing WebSocket: {close_error}", exc_info=True)
                self.flush()
                time.sleep(self.reconnect_delay)

    def publish(self, message: Dict):
        """
        Publishes a message to the stream after processing it.

        Args:
            message (Dict): The message to be published.
        """
        try:
            key: Any = self.key_func(message) if self.key_func else None
            value: Dict = self.value_func(message)
            headers: Dict = self.headers_func(message) if self.headers_func else {}
            timestamp_ms: int = self.timestamp_func(message) if self.timestamp_func else int(time.time() * 1000)
            logger.debug(f"Serializing message with key: {key}, value: {value}, headers: {headers}, timestamp_ms: {timestamp_ms}")
            msg = self.serialize(key=key, value=value, headers=headers, timestamp_ms=timestamp_ms)
            self.produce(msg.key, msg.value, msg.headers, timestamp_ms)
        except Exception as e:
            logger.error(f"Error in publish: {e}", exc_info=True)

