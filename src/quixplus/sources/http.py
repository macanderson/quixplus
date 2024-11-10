# flake8: noqa: E501
import asyncio
import json
import logging
from enum import StrEnum
from typing import Any, Callable, Dict, List, Optional, Union

import aiohttp
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from cachetools import TTLCache
from jsonpath_ng import parse
from quixstreams.models import Topic
from quixstreams.sources.base.source import Source

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


class AuthType(StrEnum):
    """Enumeration of supported authentication types."""
    BEARER = "bearer"
    BASIC = "basic"
    CUSTOM = "custom"


class HttpSource(Source):
    """
    HTTP polling source for Quixstreams with dynamic JSON root handling, TTL-based deduplication,
    and optional custom headers/timestamps for Kafka messages.

    Features:
        - Dynamic root JSONPath to extract the main object(s).
        - TTL-based deduplication to prevent memory growth.
        - Iterates over JSON arrays or handles singleton objects seamlessly.
        - Supports custom headers and timestamp generation via callables.

    Attributes:
        name (str): The name of the source.
        url (str): The URL to poll.
        poll_interval (float): Time interval for polling in seconds.
        auth_type (Optional[AuthType]): Type of authentication for the HTTP request.
        auth_credentials (Optional[Union[str, Dict[str, str]]]): Credentials for authentication.
        root_json_path (Optional[str]): JSONPath for the root object(s).
        key_json_path (Optional[str]): JSONPath for extracting the message key.
        validate (Callable): Validation function for processed data.
        transform (Callable): Transformation function for processed data.
        deduplicate (bool): Whether to prevent duplicate message production.
        deduplication_ttl (int): Time-to-live for deduplication keys in seconds.
        custom_headers_func (Optional[Callable]): Function to generate custom headers for each message.
        timestamp_func (Optional[Callable]): Function to generate a custom timestamp for each message.
    """

    def __init__(
        self,
        name: str,
        url: str,
        poll_interval: float=5.0,
        auth_type: Optional[AuthType]=None,
        auth_credentials: Optional[Union[str, Dict[str, str]]]=None,
        root_json_path: Optional[str]=None,
        key_json_path: Optional[str]=None,
        schedule_cron: Optional[str]=None,
        shutdown_timeout: float=10,
        validate: Callable[[Dict[str, Any]], bool]=lambda x: True,
        transform: Callable[[Dict[str, Any]], Dict[str, Any]]=lambda x: x,
        deduplicate: bool=True,
        deduplication_ttl: int=300,  # Default: deduplicate over the last 5 minutes
        custom_headers_func: Optional[Callable[['HttpSource', Dict[str, Any]], Dict[str, str]]]=None,
        timestamp_func: Optional[Callable[['HttpSource', Dict[str, Any]], int]]=None,
    ) -> None:
        """
        Initialize the HttpSource.

        Args:
            name (str): The name of the source.
            url (str): The URL to poll.
            poll_interval (float): How frequently to poll the endpoint, in seconds.
            auth_type (Optional[AuthType]): Type of authentication (AuthType.BEARER, AuthType.BASIC, AuthType.CUSTOM).
            auth_credentials (Optional[Union[str, Dict[str, str]]]): Authentication credentials.
            root_json_path (Optional[str]): JSONPath for the root object(s).
            key_json_path (Optional[str]): JSONPath for the Kafka message key.
            schedule_cron (Optional[str]): Cron-style schedule for polling.
            shutdown_timeout (float): Time to wait for graceful shutdown.
            validate (Callable[[Dict[str, Any]], bool]): Validation function for processed data.
            transform (Callable[[Dict[str, Any]], Dict[str, Any]]): Transformation function for processed data.
            deduplicate (bool): Prevent duplicate message production.
            deduplication_ttl (int): Time-to-live for deduplication keys in seconds.
            custom_headers_func (Optional[Callable]): Function to generate custom headers for messages.
            timestamp_func (Optional[Callable]): Function to generate a custom timestamp in milliseconds.
        """
        super().__init__(name, shutdown_timeout)
        self.url = url
        self.poll_interval = poll_interval
        self.auth_type = auth_type
        self.auth_credentials = auth_credentials
        self.root_json_path = parse(root_json_path) if root_json_path else None
        self.key_json_path = parse(key_json_path) if key_json_path else None
        self.schedule_cron = schedule_cron
        self.validate = validate
        self.transform = transform
        self.deduplicate = deduplicate
        self.deduplication_ttl = deduplication_ttl
        self.custom_headers_func = custom_headers_func
        self.timestamp_func = timestamp_func

        # TTLCache for deduplication
        self.seen_keys = TTLCache(maxsize=100_000, ttl=deduplication_ttl)

        self.scheduler = AsyncIOScheduler()
        if schedule_cron:
            self.scheduler.add_job(self._start_polling, CronTrigger.from_crontab(schedule_cron))

    async def _get_auth_headers(self) -> Dict[str, str]:
        """Prepare HTTP headers for authentication."""
        headers = {}
        if self.auth_type == AuthType.BEARER:
            headers["Authorization"] = f"Bearer {self.auth_credentials}"
        elif self.auth_type == AuthType.BASIC and isinstance(self.auth_credentials, tuple):
            from aiohttp.helpers import BasicAuth
            headers["Authorization"] = BasicAuth(*self.auth_credentials).encode()
        elif self.auth_type == AuthType.CUSTOM and isinstance(self.auth_credentials, dict):
            headers.update(self.auth_credentials)
        return headers

    async def poll_endpoint(self):
        """Polls the HTTP endpoint and processes the response."""
        async with aiohttp.ClientSession() as session:
            while self._running:
                try:
                    headers = await self._get_auth_headers()
                    async with session.get(self.url, headers=headers) as response:
                        if response.status == 200:
                            data = await response.json()
                            self._process_response(data)
                        else:
                            logger.error(f"Failed to fetch data: HTTP {response.status}")
                except Exception as e:
                    logger.error(f"Error during polling: {e}")
                await asyncio.sleep(self.poll_interval)

    def _process_response(self, data: Any):
        """Processes the response data dynamically."""
        root_data = self._extract_json_path(data, self.root_json_path) or data

        if isinstance(root_data, list):
            for item in root_data:
                self._produce_message(item)
        elif isinstance(root_data, dict):
            self._produce_message(root_data)
        else:
            logger.warning("Unsupported root data format: Expected list or dict.")

    def _produce_message(self, item: Dict[str, Any]):
        """Validates, transforms, serializes, and produces a Kafka message."""
        if not self.validate(item):
            return
        transformed = self.transform(item)
        key = self._extract_json_path(transformed, self.key_json_path)

        if self.deduplicate and key:
            if key in self.seen_keys:
                logger.debug(f"Duplicate message detected for key: {key}")
                return
            self.seen_keys[key] = True  # Add key to the TTL cache

        headers = self.custom_headers_func(self, transformed) if self.custom_headers_func else {}
        timestamp = self.timestamp_func(self, transformed) if self.timestamp_func else None

        msg = self.serialize(key=key, value=transformed, headers=headers, timestamp=timestamp)

        self.produce(key=msg.key, value=msg.value, headers=msg.headers, timestamp=msg.timestamp)
        logger.info(f"Produced message for key: {key}")

    def _extract_json_path(self, data: Any, json_path) -> Optional[Any]:
        """Extracts data using JSONPath."""
        if not json_path:
            return None
        try:
            matches = json_path.find(data)
            return matches[0].value if matches else None
        except Exception as e:
            logger.error(f"Error extracting JSONPath: {e}")
            return None

    async def _start_polling(self):
        """Starts polling asynchronously."""
        await self.poll_endpoint()

    def run(self):
        """Starts polling or scheduler."""
        if self.schedule_cron:
            self.scheduler.start()
            asyncio.get_event_loop().run_forever()
        else:
            asyncio.run(self.poll_endpoint())

    def stop(self):
        """Stops polling and scheduler."""
        self._running = False
        if self.scheduler._running:
            self.scheduler.shutdown()
        logger.info("HTTP source stopped.")


__all__ = ['HttpSource']
