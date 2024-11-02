import asyncio
import json
import logging
from typing import Any, Callable, Dict, Optional, Union

import aiohttp
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from jsonpath_ng import parse
from quixstreams.models import Topic
from quixstreams.sources.base.source import BaseSource

logger = logging.getLogger(__name__)
# Configure logger to pretty print
logging.basicConfig(level=logging.INFO)


class HttpSource(BaseSource):
    """
    HTTP polling source for Quixstreams, polling a specified URL at intervals or on a schedule.

    Features:
        - Supports JSONPath to extract parts of the response for key and value fields.
        - Can authenticate requests with bearer tokens, basic auth, or custom headers.
        - Produces messages to Kafka based on cron-like scheduling or regular intervals.

    Attributes:
        url (str): The URL to poll.
        poll_interval (float): Time interval for polling the URL in seconds.
        auth_type (Optional[str]): Type of authentication for the HTTP request.
        auth_credentials (Optional[Union[str, Dict[str, str]]]): Credentials for authentication.
        key_json_path (Optional[str]): JSONPath for extracting the message key.
        value_json_path (Optional[str]): JSONPath for extracting the message value.
        schedule_cron (Optional[str]): Cron expression to schedule polling times.
        key_serializer (Callable): Serializer for the message key.
        value_serializer (Callable): Serializer for the message value.
    """

    def __init__(
        self,
        url: str,
        poll_interval: float = 5.0,
        auth_type: Optional[str] = None,
        auth_credentials: Optional[Union[str, Dict[str, str]]] = None,
        key_json_path: Optional[str] = None,
        value_json_path: Optional[str] = None,
        schedule_cron: Optional[str] = None,
        name: Optional[str] = None,
        shutdown_timeout: float = 10,
        key_serializer: Callable[[Any], str] = str,
        value_serializer: Callable[[Any], str] = json.dumps,
    ) -> None:
        """
        Initialize the HttpSource.

        Args:
            url (str): The URL to poll.
            poll_interval (float): How frequently to poll the endpoint, in seconds.
            auth_type (Optional[str]): Type of authentication ('bearer', 'basic', 'custom').
            auth_credentials (Optional[Union[str, Dict[str, str]]]): Authentication credentials.
            key_json_path (Optional[str]): JSONPath to extract the key for Kafka messages.
            value_json_path (Optional[str]): JSONPath to extract the value for Kafka messages.
            schedule_cron (Optional[str]): Cron-style schedule string for specific hours.
            name (Optional[str]): The name of the source.
            shutdown_timeout (float): Time to wait for a graceful shutdown.
            key_serializer (Callable[[Any], str]): Serializer for the message key.
            value_serializer (Callable[[Any], str]): Serializer for the message value.
        """
        super().__init__(name or url, shutdown_timeout)
        self.url = url
        self.poll_interval = poll_interval
        self.auth_type = auth_type
        self.auth_credentials = auth_credentials
        self.key_json_path = parse(key_json_path) if key_json_path else None
        self.value_json_path = parse(value_json_path) if value_json_path else None
        self.schedule_cron = schedule_cron
        self.key_serializer = key_serializer
        self.value_serializer = value_serializer
        self.scheduler = AsyncIOScheduler()
        if schedule_cron:
            self.scheduler.add_job(self._start_polling, CronTrigger.from_crontab(schedule_cron))

    async def _get_auth_headers(self) -> Dict[str, str]:
        """Prepare the HTTP headers based on authentication type and credentials."""
        headers = {}
        if self.auth_type == "bearer":
            headers["Authorization"] = f"Bearer {self.auth_credentials}"
        elif self.auth_type == "basic" and isinstance(self.auth_credentials, tuple):
            from aiohttp.helpers import BasicAuth
            headers["Authorization"] = BasicAuth(*self.auth_credentials).encode()
        elif self.auth_type == "custom" and isinstance(self.auth_credentials, dict):
            headers.update(self.auth_credentials)
        return headers

    async def poll_endpoint(self):
        """
        Polls the HTTP endpoint, processes the response, and sends the extracted data to Kafka.
        """
        async with aiohttp.ClientSession() as session:
            while self.running:
                try:
                    headers = await self._get_auth_headers()
                    async with session.get(self.url, headers=headers) as response:
                        if response.status == 200:
                            data = await response.json()
                            key = self._extract_json_path(data, self.key_json_path)
                            serialized_key = self.key_serializer(key) if key else None
                            value = self._extract_json_path(data, self.value_json_path) or data
                            serialized_value = self.value_serializer(value)
                            msg = self.serialize(key=serialized_key, value=serialized_value)
                            self.produce(
                                key=msg.key,
                                value=msg.value,
                                timestamp=msg.timestamp,
                                headers=msg.headers
                            )
                            logger.info(f"Produced message for key: {serialized_key}")
                        else:
                            logger.error(f"Failed to fetch data: HTTP {response.status}")
                except Exception as e:
                    logger.error(f"Error during polling or message production: {e}")
                await asyncio.sleep(self.poll_interval)

    def _extract_json_path(self, data: dict, json_path) -> Optional[Any]:
        """
        Extracts data from JSON using JSONPath.

        Args:
            data (dict): The JSON response data.
            json_path (str): JSONPath expression to extract the required value.

        Returns:
            Optional[Any]: The extracted data or None if extraction fails.
        """
        if not json_path:
            return None
        try:
            matches = json_path.find(data)
            return matches[0].value if matches else None
        except Exception as e:
            logger.error(f"Error extracting JSON path {json_path} from data: {e}")
            return None

    async def _start_polling(self):
        """Starts polling asynchronously within scheduled hours if defined."""
        await self.poll_endpoint()

    def run(self):
        """
        Starts the polling loop using asyncio, respecting the scheduling if a cron expression is provided.
        """
        if self.schedule_cron:
            self.scheduler.start()
            asyncio.get_event_loop().run_forever()
        else:
            asyncio.run(self.poll_endpoint())

    def stop(self):
        """Stops polling and shuts down the scheduler if it’s active."""
        self.running = False
        if self.scheduler.running:
            self.scheduler.shutdown()
        logger.info("HTTP source stopped.")

    def default_topic(self) -> Topic:
        """Returns the default Kafka topic configuration."""
        return Topic(
            name=self.name,
            key_serializer="string",
            key_deserializer="string",
            value_serializer="json",
            value_deserializer="json",
        )

__all__ = ["HttpSource"]
