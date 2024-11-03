"""
WebsocketSource

for use with quixstreams library

requires: quixstreams, websocket-client

This module provides a WebsocketSource class that connects to a WebSocket,
receives data, and sends it to a Kafka topic using the quixstreams library.
"""

import json
import logging
import sys
import threading
import time
from typing import Any, Callable, List, Optional, Tuple

import websocket
from quixstreams.checkpointing.exceptions import CheckpointProducerTimeout  # noqa: E501
from quixstreams.models import (  # import models for type annotations
    Headers,
    MessageKey,
    MessageValue,
    TimestampType,
    Topic,
)
from quixstreams.sources.base.source import BaseSource

logger = logging.getLogger(__name__)
handler = logging.StreamHandler(sys.stdout)
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.setLevel(logging.INFO)


class WebsocketSource(BaseSource):
    """
    WebSocket-based source class for receiving data from a WebSocket and sending it to a Kafka topic.

    Attributes:
        topic_name (str): The name of the Kafka topic.
        ws_url (str): The WebSocket URL to connect to.
        transform (Callable[[str], dict]): Function to transform the received message.
        validator (Optional[Callable[[str], bool]]): Function to validate the received message.
        key_serializer (Callable): Function to serialize the message key.
        value_serializer (Callable): Function to serialize the message value.
        key_field (Optional[str]): Field to use as the message key.
        timestamp_field (Optional[str]): Field to use as the message timestamp.
        auth_payload (Optional[dict]): Payload for WebSocket authentication.
        subscribe_payload (Optional[dict]): Payload for WebSocket subscription.
        reconnect_delay (int): Delay before reconnecting to the WebSocket.
        shutdown_timeout (int): Timeout for graceful shutdown.
        _running (bool): Indicates if the WebsocketSource is running.
    """

    def __init__(
        self,
        topic_name: str,
        ws_url: str,
        transform: Callable[[str], dict],
        validator: Optional[Callable[[str], bool]] = None,
        key_serializer: Callable = str,
        value_serializer: Callable = json.dumps,
        key_field: Optional[str] = None,
        timestamp_field: Optional[str] = None,
        auth_payload: Optional[dict] = None,
        subscribe_payload: Optional[dict] = None,
        reconnect_delay: int = 2,
        shutdown_timeout: int = 10,
    ):
        """
        Initialize the WebsocketSource.

        Args:
            topic_name (str): The name of the Kafka topic.
            ws_url (str): The WebSocket URL to connect to.
            transform (Callable[[str], dict]): Function to transform the
                received message.
            validator (Optional[Callable[[str], bool]]): Function to validate
                the received message.
            key_serializer (Callable): Function to serialize the message key.
            value_serializer (Callable): Function to serialize the message
                value.
            key_field (Optional[str]): Field to use as the message key.
            timestamp_field (Optional[str]): Field to use as the
                message timestamp.
            auth_payload (Optional[dict]): Payload for WebSocket
                authentication.
            subscribe_payload (Optional[dict]): Payload for WebSocket
                subscription.
            reconnect_delay (int): Delay before reconnecting to the WebSocket.
            shutdown_timeout (int): Timeout for graceful shutdown.

        Examples:
            >>> ws_source = WebsocketSource(
            ...     topic_name="example_topic",
            ...     ws_url="wss://example.com/socket",
            ...     transform=lambda x: json.loads(x),
            ...     validator=lambda x: "key" in x,
            ...     key_field="key",
            ...     timestamp_field="timestamp"
            ... )
        """
        super().__init__()
        self.topic_name = topic_name
        self.ws_url = ws_url
        self.transform = transform
        self.validator = validator or (lambda x: True)  # Default to always true if not provided
        self.key_serializer = key_serializer
        self.value_serializer = value_serializer
        self.key_field = key_field
        self.timestamp_field = timestamp_field
        self.auth_payload = auth_payload
        self.subscribe_payload = subscribe_payload
        self.reconnect_delay = reconnect_delay
        self.shutdown_timeout = shutdown_timeout
        self._running = False

    def start(self):
        """
        Start the WebsocketSource by connecting to the WebSocket.

        Raises:
            Exception: If the connection to the WebSocket fails.
        """
        logger.info(f"Connecting to WebSocket at {self.ws_url}...")
        self._running = True
        try:
            self._connect_to_websocket()
        except Exception as e:
            logger.error(f"Failed to connect to WebSocket: {e}")
            self.cleanup(failed=True)
            raise
        else:
            self.cleanup(failed=False)

    def stop(self):
        """
        Stop the WebsocketSource and close the WebSocket connection.
        """
        logger.info("Stopping WebsocketSource...")
        super().stop()
        self.flush(self.shutdown_timeout)
        self._running = False
        if hasattr(self, "ws"):
            self.ws.close()

    def cleanup(self, failed: bool) -> None:
        """
        Cleanup resources after stopping the WebsocketSource.

        Args:
            failed (bool): Indicates if the cleanup is due to a failure.
        """
        if not failed:
            self.flush(self.shutdown_timeout / 2)

    def flush(self, timeout: Optional[float] = None) -> None:
        """
        Flush the producer to ensure all messages are sent.

        Args:
            timeout (Optional[float]): Timeout for the flush operation.

        Raises:
            CheckpointProducerTimeout: If messages fail to be produced before
            the timeout.
        """
        logger.info("Flushing source")
        unproduced_msg_count = self._producer.flush(timeout)
        if unproduced_msg_count > 0:
            raise CheckpointProducerTimeout(
                f"'{unproduced_msg_count}' messages failed to be produced before the producer flush timeout"  # noqa: E501
            )

    def default_topic(self) -> Topic:
        """
        Get the default Kafka topic configuration.

        Returns:
            Topic: The default Kafka topic configuration.
        """
        return Topic(
            name=self.topic_name,
            value_serializer=self.value_serializer,
            key_serializer=self.key_serializer,
            timestamp_extractor=self._extract_timestamp,
        )

    def _extract_timestamp(
        self,
        value: Any,
        headers: Optional[List[Tuple[str, bytes]]],
        timestamp: float,
        timestamp_type: TimestampType,
    ) -> int:
        """
        Extract the timestamp from the message value.

        Args:
            value (Any): The message value.
            headers (Optional[List[Tuple[str, bytes]]]): The message headers.
            timestamp (float): The message timestamp.
            timestamp_type (TimestampType): The type of the timestamp.

        Returns:
            int: The extracted timestamp.
        """
        return value.get(self.timestamp_field, int(time.time() * 1000))

    def _on_message(self, ws: websocket.WebSocketApp, data: str):
        """
        Handle incoming WebSocket messages.

        Args:
            ws (websocket.WebSocketApp): The WebSocket application instance.
            data (str): The received message data.
        """
        try:
            # Validate message
            if not self.validator(data):
                logger.debug("Message ignored by validator.")
                return  # Skip processing if the message fails validation

            # Pass validated message to the transform function
            record_value = self.transform(data)
            record_timestamp = record_value.get(self.timestamp_field, int(time.time() * 1000))
            record_key = record_value.get(self.key_field) if self.key_field else None
            self.produce(
                key=record_key,
                value=record_value,
                timestamp=record_timestamp,
            )
        except Exception as e:
            logger.error(f"Failed to process data: {e}")

    def _connect_to_websocket(self):
        """
        Connect to the WebSocket and set up event handlers.
        """

        def on_open(ws: websocket.WebSocketApp):
            """
            Handle WebSocket connection open event.

            Args:
                ws (websocket.WebSocketApp): The WebSocket application instance.  # noqa: E501
            """
            logger.info("WebSocket connection opened.")
            if self.auth_payload:
                ws.send(json.dumps(self.auth_payload))
                logger.info("Sent authentication payload.")
            if self.subscribe_payload:
                ws.send(json.dumps(self.subscribe_payload))
                logger.info("Sent subscription payload.")

        def on_error(ws: websocket.WebSocketApp, error: str):
            """
            Handle WebSocket error event.

            Args:
                ws (websocket.WebSocketApp): The WebSocket application instance.  # noqa: E501
                error (str): The error message.
            """
            logger.error(f"WebSocket error: {error}")
            self.cleanup(failed=True)
            raise

        def on_close(ws: websocket.WebSocketApp, close_status_code: int, close_msg: str):  # noqa: E501
            """
            Handle WebSocket connection close event.

            Args:
                ws (websocket.WebSocketApp): The WebSocket application instance.  # noqa: E501
                close_status_code (int): The close status code.
                close_msg (str): The close message.
            """
            logger.info("WebSocket connection closed.")
            time.sleep(self.reconnect_delay)
            self.cleanup(failed=False)
            if self._running:
                self._connect_to_websocket()

        self.ws = websocket.WebSocketApp(
            self.ws_url,
            on_open=on_open,
            on_message=self._on_message,
            on_error=on_error,
            on_close=on_close,
        )
        threading.Thread(target=self.ws.run_forever).start()

    def produce(
        self,
        value: MessageValue,
        key: MessageKey = None,
        headers: Headers = None,
        timestamp: int = None,
    ):
        """
        Produce a message to the Kafka topic.

        Args:
            value (MessageValue): The message value.
            key (MessageKey, optional): The message key. Defaults to None.
            headers (Headers, optional): The message headers. Defaults to None.
            timestamp (int, optional): The message timestamp. Defaults to None.
        """
        try:
            serialized_value = (
                self.value_serializer(value).encode("utf-8")
                if not isinstance(value, bytes)
                else value
            )
            serialized_key = (
                self.key_serializer(key).encode("utf-8") if key is not None else None  # noqa: E501
            )
            self._producer.produce(
                topic=self.topic_name,
                headers=headers,
                key=serialized_key,
                value=serialized_value,
                timestamp=timestamp,
            )
            logger.info(
                f"Produced record to topic '{self.topic_name}': {key}, {json.dumps(value, indent=4)}"  # noqa: E501
            )
        except Exception as e:
            logger.error(f"Failed to produce record: {e}")


__all__ = ["WebsocketSource"]
