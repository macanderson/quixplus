"""Custom websocket source for use with Quixstreams."""
from datetime import datetime
import json
import logging
import threading
from typing import Callable, Optional, Union

from quixstreams.sources.base.source import Source
import websocket


logger = logging.getLogger(__name__)


class WebsocketSource(Source):
    """
    A source that reads messages from a WebSocket connection.

    Attributes:
        ws_url (str): The complete WebSocket URL to connect to.
        auth_payload (dict | None): The authentication message to send to the WebSocket.
        subscribe_payload (dict | None): The subscription message to send to the WebSocket.
        validator (Callable[[dict], bool] | None): A function to validate incoming messages.
        transform (Callable[[dict], dict] | None): A function to transform incoming messages.
        key_fields (list[str] | None): The fields to use as the key for the message.
        timestamp_field (str | None): The field to use as the timestamp for the message.
        debug (bool): Whether to log debug messages.

    Example:

    ```python
    ws_url = "wss://ws-feed.pro.coinbase.com"
    subscribe_payload = {
        "type": "subscribe",
        "product_ids": ["BTC-USD"],
        "channels": ["ticker"]
    }
    source = WebsocketSource(
        ws_url=ws_url,
        subscribe_payload=subscribe_payload,
        key_fields=["product_id"],
        timestamp_field="time",
        debug=True
    )

    app = Application()
    topic = app.topic("coinbase_btc_usd")
    app.add_source(source, topic)
    app.run()
    ```

    """

    def __init__(
        self,
        name: str,
        ws_url: str,
        auth_payload: Union[dict, None]=None,
        subscribe_payload: Union[dict, None]=None,
        validator: Optional[Callable[[dict], bool]]=None,
        transform: Optional[Callable[[dict], dict]]=None,
        key_fields: Optional[list[str]]=None,
        timestamp_field: Optional[str]=None,
        debug: bool=False
    ):
        super().__init__(name)
        logger.info(f"Initializing WebsocketSource with ws_url: {ws_url}")
        self.ws_url = ws_url
        self.auth_payload = auth_payload
        self.subscribe_payload = subscribe_payload
        self.validator: Optional[Callable[[dict], bool]] = validator
        self.transform: Optional[Callable[[dict], dict]] = transform
        self.key_fields = key_fields
        self.timestamp_field = timestamp_field
        self.debug = debug
        self.ws = None

    def on_open(self, ws):
        """
        Callback for when the WebSocket connection is opened.
        """
        logger.info("WebSocket connection opened")
        if hasattr(self, 'auth_payload') and self.auth_payload:
            ws.send(json.dumps(self.auth_payload))
            logger.info("Sent authentication payload")

        if hasattr(self, 'subscribe_payload') and self.subscribe_payload:
            ws.send(json.dumps(self.subscribe_payload))
            logger.info("Sent subscription payload")

    def on_message(self, ws, message):
        """
        Callback for when a message is received from the WebSocket.
        """
        message = json.loads(message)
        if self.debug:
            logger.info(f"Received message: {message}")
        if self.validator and not self.validator(message):
            logger.error(f"Invalid message: {message}")
            return

        if self.transform:
            message = self.transform(message)

        if self.key_fields:
            key_data = {field: message[field] for field in self.key_fields}
        else:
            key_data = {}

        if self.timestamp_field:
            print("timestamp >>>:::", self.timestamp_field)
            timestamp = message[self.timestamp_field]
        else:
            timestamp = datetime.now()

        msg = self.serialize(
            key=key_data,
            message=message,
            timestamp=timestamp
        )
        self.produce(
            key=msg.key,
            message=msg.message,
            timestamp=msg.timestamp
        )

    def on_error(self, ws, error):
        """
        Callback for when an error occurs with the WebSocket.
        """
        logger.error(f"WebSocket error: {error}")
        self.running = False
        self.flush()
        self.reconnect()

    def reconnect(self):
        """
        Attempts to reconnect the WebSocket connection.
        """
        logger.info("Attempting to reconnect WebSocket")
        self.running = True
        self.run()

    def on_close(self, ws, close_status_code, close_msg):
        """
        Callback for when the WebSocket connection is closed.
        """
        logger.info("WebSocket connection closed")
        self.flush()
        self.running = False
        self.reconnect()

    def run(self):
        """
        Starts the WebSocket connection and sends random numbers.
        """
        while self.running:
            self.ws = websocket.WebSocketApp(
                self.ws_url,
                on_open=self.on_open,
                on_message=self.on_message,
                on_error=self.on_error,
                on_close=self.on_close
            )

            wst = threading.Thread(target=self.ws.run_forever)
            wst.daemon = True
            wst.start()
        # finally close the connection
        self.ws.close()
