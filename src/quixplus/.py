import asyncio
from datetime import datetime
import json
import logging
from typing import Any, Dict, Optional, Set, Union

import aiohttp
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from jsonpath_ng import parse
from quixstreams.sources.base.source import Source


logger = logging.getLogger(__name__)
# Configure logger to pretty print
logging.basicConfig(level=logging.INFO)


class HttpSource(Source):
    """
    HTTP polling source for Quixstreams, polling a specified URL at intervals or on a schedule.

    Features:
        - Supports JSONPath to extract parts of the response for key and value fields.
        - Can authenticate requests with bearer tokens, basic auth, or custom headers.
        - Prevents sending duplicate data when polling endpoints that return lists or single objects.
    """

    def __init__(
        self,
        name: str,
        url: str,
        poll_interval: float=5.0,
        auth_type: Optional[str]=None,
        auth_credentials: Optional[Union[str, Dict[str, str]]]=None,
        key_json_path: Optional[str]=None,
        value_json_path: Optional[str]=None,
        schedule_cron: Optional[str]=None,
        id_json_path: Optional[str]=None,
    ) -> None:
        """
        Initialize the HttpSource.

        Args:
            name (str): The name of the source.
            url (str): The URL to poll.
            poll_interval (float): How frequently to poll the endpoint, in seconds.
            auth_type (Optional[str]): Type of authentication ('bearer', 'basic', 'custom').
            auth_credentials (Optional[Union[str, Dict[str, str]]]): Authentication credentials.
            key_json_path (Optional[str]): JSONPath to extract the key from each item.
            value_json_path (Optional[str]): JSONPath to extract the value from each item.
            schedule_cron (Optional[str]): Cron-style schedule string for specific hours.
            id_json_path (Optional[str]): JSONPath to extract unique ID from each item.
        """
        super().__init__(name)
        self.url = url
        self.poll_interval = poll_interval
        self.auth_type = auth_type
        self.auth_credentials = auth_credentials
        self.key_json_path = parse(key_json_path) if key_json_path else None
        self.value_json_path = parse(value_json_path) if value_json_path else None
        self.timestamp_json_path = parse(timestamp_json_path) if timestamp_json_path else None
        self.id_json_path = parse(id_json_path) if id_json_path else None
        self.schedule_cron = schedule_cron
        self.scheduler = AsyncIOScheduler()
        self.processed_ids: Set[Any] = set()
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

    def extract_timestamp(json_path: str, data: dict) -> Optional[str]:
        """
        Extracts a timestamp from JSON using JSONPath.

        Args:
            json_path (str): The JSONPath expression.
            data (dict): The JSON data.

        Returns:
            Optional[str]: The extracted timestamp or None if extraction fails.
        """
        if not json_path:
            return datetime.now().timestamp()
        try:
            matches = json_path.find(data)
            if matches:
                matched_value = matches[0].v
                return datetime.fromisoformat(matches[0].value).timestamp()
            else:
                return datetime.now().timestamp()
        except Exception as e:
            logger.error(f"Error extracting timestamp from data: {e}")
            return None

    async def poll_endpoint(self):
        """
        Polls the HTTP endpoint, processes the response, and avoids sending duplicates.
        Supports endpoints that return either single objects or lists of objects.
        """
        async with aiohttp.ClientSession() as session:
            while self.running:
                try:
                    headers = await self._get_auth_headers()
                    async with session.get(self.url, headers=headers) as response:
                        if response.status == 200:
                            data = await response.json()
                            if isinstance(data, list):
                                items = data
                            else:
                                items = [data]
                            new_items = self._filter_new_items(items)
                            for item in new_items:
                                key = self._extract_json_path(item, self.key_json_path)
                                value = self._extract_json_path(item, self.value_json_path) or item
                                # Process the key and value as needed
                                msg = self.serialize(key=key, value=value, timestamp=self.get_timestamp(value))
                                logger.info(f"Processed new item with key: {key}")
                        else:
                            logger.error(f"Failed to fetch data: HTTP {response.status}")
                except Exception as e:
                    logger.error(f"Error during polling or data processing: {e}")
                await asyncio.sleep(self.poll_interval)

    def _filter_new_items(self, items: list) -> list:
        """
        Filters out items that have already been processed based on their unique IDs.

        Args:
            items (list): The list of items returned from the endpoint.

        Returns:
            list: A list of new items that haven't been processed yet.
        """
        new_items = []
        for item in items:
            item_id = self._extract_json_path(item, self.id_json_path)
            if item_id is None:
                # If no ID is extracted, consider item as new
                new_items.append(item)
            elif item_id not in self.processed_ids:
                self.processed_ids.add(item_id)
                new_items.append(item)
        return new_items

    def _extract_json_path(self, data: dict, json_path) -> Optional[Any]:
        """
        Extracts data from JSON using JSONPath.

        Args:
            data (dict): The JSON data.
            json_path (jsonpath_ng.JSONPath): Parsed JSONPath expression.

        Returns:
            Optional[Any]: The extracted data or None if extraction fails.
        """
        if not json_path:
            return None
        try:
            matches = json_path.find(data)
            return matches[0].value if matches else None
        except Exception as e:
            logger.error(f"Error extracting JSON path from data: {e}")
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


__all__ = ["HttpSource"]
