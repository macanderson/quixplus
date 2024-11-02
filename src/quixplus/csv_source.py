import csv
import json
import logging
from typing import Any, Callable, List, Optional

from quixstreams.models import Topic
from quixstreams.sources.base.source import BaseSource

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


class CSVSource(BaseSource):
    """
    A CSV source that reads data from a CSV file and produces messages with a JSON payload
    and an optional composite key for Kafka.

    Attributes:
        path (str): The path to the CSV file.
        key_columns (Optional[List[str]]): List of columns to construct the Kafka message key.
        key_separator (str): Separator to use between key column values if multiple are specified.
        dialect (str): CSV dialect to use for parsing the file.
        key_serializer (Callable): Serializer for the message key.
        value_serializer (Callable): Serializer for the message value.
    """

    def __init__(
        self,
        path: str,
        key_columns: Optional[List[str]] = None,
        key_separator: str = "_",
        dialect: str = "excel",
        name: Optional[str] = None,
        shutdown_timeout: float = 10,
        key_serializer: Callable[[Any], str] = str,
        value_serializer: Callable[[Any], str] = json.dumps,
    ) -> None:
        """
        Initializes the CSV source for Kafka message production.

        Args:
            path (str): Path to the CSV file.
            key_columns (Optional[List[str]]): List of columns to construct the Kafka message key.
            key_separator (str): Separator to use between key column values if multiple are specified.
            dialect (str): CSV dialect to use for parsing the file.
            name (Optional[str]): The name of the source.
            shutdown_timeout (float): Time to wait for a graceful shutdown.
            key_serializer (Callable[[Any], str]): Serializer for the message key.
            value_serializer (Callable[[Any], str]): Serializer for the message value.

        Example:
            >>> source = CSVSource(
            ...     path="data.csv",
            ...     key_columns=["id", "timestamp"],
            ...     key_separator="-",
            ...     dialect="excel"
            ... )
        """
        super().__init__(name or path, shutdown_timeout)
        self.path = path
        self.key_columns = key_columns or []
        self.key_separator = key_separator
        self.dialect = dialect
        self.key_serializer = key_serializer
        self.value_serializer = value_serializer

    def run(self):
        """
        Reads the CSV file and produces each row as a Kafka message.
        """
        with open(self.path, "r") as f:
            reader = csv.DictReader(f, dialect=self.dialect)

            while self.running:
                try:
                    item = next(reader)
                except StopIteration:
                    logger.info("Reached end of CSV file.")
                    return
                except Exception as e:
                    logger.error(f"Error reading CSV file: {e}")
                    return

                # Construct the key by concatenating specified columns
                key = (
                    self.key_separator.join([str(item[col]) for col in self.key_columns if col in item])
                    if self.key_columns
                    else None
                )

                try:
                    # Serialize the row as a JSON value
                    value = self.value_serializer(item)
                    msg = self.serialize(
                        key=self.key_serializer(key) if key else None,
                        value=value,
                        timestamp_ms=None  # Can add timestamp processing if needed
                    )
                    self.produce(
                        key=msg.key,
                        value=msg.value,
                        timestamp=msg.timestamp,
                        headers=msg.headers
                    )
                    logger.info(f"Produced message for key: {key}")
                except Exception as e:
                    logger.error(f"Error serializing or producing message: {e}")

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