import csv
import json
import logging
from typing import Any, Callable, Dict, List, Optional

from quixstreams.models import Topic
from quixstreams.sources.base.source import Source

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


class CSVSource(Source):
    """
    A CSV source for Quixstreams that reads data from a CSV file and produces messages.

    Features:
        - Supports configurable composite keys using specified CSV columns.
        - Allows dynamic timestamp and headers generation through callables.
        - Dynamically processes CSV rows into Kafka messages.

    Attributes:
        path (str): Path to the CSV file.
        dialect (str): CSV dialect for parsing.
        key_func (Optional[Callable[['CSVSource', Dict[str, Any]], Any]]): Function to generate the Kafka message key.
        timestamp_func (Optional[Callable[['CSVSource', Dict[str, Any]], int]]): Function to generate message timestamps.
        headers_func (Optional[Callable[['CSVSource', Dict[str, Any]], Dict[str, str]]]): Function to generate custom headers.
    """

    def __init__(
        self,
        name: str,
        path: str,
        dialect: str="excel",
        key_func: Optional[Callable[['CSVSource', Dict[str, Any]], Any]]=None,
        timestamp_func: Optional[Callable[['CSVSource', Dict[str, Any]], int]]=None,
        headers_func: Optional[Callable[['CSVSource', Dict[str, Any]], Dict[str, str]]]=None,
    ) -> None:
        """
        Initializes the CSV source for Quixstreams.

        Args:
            name (str): Name of the source.
            path (str): Path to the CSV file.
            dialect (str): CSV dialect for parsing.
            key_func (Optional[Callable]): Function to generate the Kafka message key.
            timestamp_func (Optional[Callable]): Function to generate message timestamps.
            headers_func (Optional[Callable]): Function to generate custom headers.
        """
        super().__init__(name)
        self.path = path
        self.dialect = dialect
        self.key_func = key_func
        self.timestamp_func = timestamp_func
        self.headers_func = headers_func
        self.running = False

    def run(self):
        """
        Reads the CSV file and produces each row as a Kafka message.
        """
        try:
            with open(self.path, "r") as file:
                reader = csv.DictReader(file, dialect=self.dialect)

                for row in reader:
                    if not self.running:
                        break

                    try:
                        key = self._generate_key(row)
                        timestamp = self._generate_timestamp(row)
                        headers = self._generate_headers(row)

                        msg = self.serialize(
                            key=key,
                            value=row,
                            timestamp=timestamp,
                            headers=headers,
                        )
                        self.produce(
                            key=msg.key,
                            value=msg.value,
                            timestamp=msg.timestamp,
                            headers=msg.headers,
                        )
                        logger.info(f"Produced message: key={key}, headers={headers}")
                    except Exception as e:
                        logger.error(f"Error processing row: {e}")
        except Exception as e:
            logger.error(f"Error opening CSV file: {e}")

    def stop(self):
        """
        Stops the CSV source.
        """
        logger.info("Stopping CSV source...")
        self.running = False

    def _generate_key(self, row: Dict[str, Any]) -> Optional[Any]:
        """
        Generates the key for a Kafka message.

        Args:
            row (Dict[str, Any]): The current CSV row.

        Returns:
            Optional[Any]: The generated key or None.
        """
        if not self.key_func:
            return None
        try:
            return self.key_func(self, row)
        except Exception as e:
            logger.error(f"Error generating key: {e}")
            return None

    def _generate_timestamp(self, row: Dict[str, Any]) -> Optional[int]:
        """
        Generates the timestamp for a Kafka message.

        Args:
            row (Dict[str, Any]): The current CSV row.

        Returns:
            Optional[int]: The generated timestamp in milliseconds or None.
        """
        try:
            if self.timestamp_func:
                return self.timestamp_func(self, row)
            return None  # Use default behavior if no timestamp_func is provided
        except Exception as e:
            logger.error(f"Error generating timestamp: {e}")
            return None

    def _generate_headers(self, row: Dict[str, Any]) -> Dict[str, str]:
        """
        Generates custom headers for a Kafka message.

        Args:
            row (Dict[str, Any]): The current CSV row.

        Returns:
            Dict[str, str]: The generated headers.
        """
        if not self.headers_func:
            return {}
        try:
            return self.headers_func(self, row)
        except Exception as e:
            logger.error(f"Error generating headers: {e}")
            return {}

    def default_topic(self) -> Topic:
        """
        Returns the default Kafka topic configuration.

        Returns:
            Topic: The default topic configuration for Kafka messages.
        """
        return Topic(
            name=self.name,
            key_serializer="string",
            key_deserializer="string",
            value_serializer="json",
            value_deserializer="json",
        )


__all__ = ["CSVSource"]
