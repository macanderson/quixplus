# flake8: noqa: E501
"""
A CSV source for Quixstreams that reads data from a CSV file and produces messages.
"""
import logging
from typing import Any, Callable, Dict, Optional

import clevercsv
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
        debug: bool=False,
    ) -> None:
        """
        Initializes the CSV source for Quixstreams.

        Args:
            name (str): Name of the source.
            path (str): Path to the CSV file.
            key_func (Optional[Callable]): Function to generate the Kafka message key.
            timestamp_func (Optional[Callable]): Function to generate message timestamps.
            headers_func (Optional[Callable]): Function to generate custom headers.
        """
        super().__init__(name)
        self.path = path
        self.key_func = key_func
        self.timestamp_func = timestamp_func
        self.headers_func = headers_func
        self._running = True
        self.debug = debug
    def run(self) -> None:
        """
        Reads the CSV file and produces each row as a Kafka message.
        """
        if not self._running:
            logger.info("Source is already stopped")
            return
        try:
            with open("data.csv", "r", newline="") as fp:
                dialect = clevercsv.Sniffer().sniff(fp.read(), verbose=self.debug)
                fp.seek(0)
                reader = clevercsv.reader(fp, dialect)
                for row in list(reader):
                    if not self._running:
                        logger.info("Stopping CSV processing")
                        break
                    try:
                        self._process_row(row)
                    except Exception as e:
                        logger.error(f"Error processing row: {e}", exc_info=True)
        except FileNotFoundError:
            logger.error(f"CSV file not found: {self.path}")
        except Exception as e:
            logger.error(f"Error reading CSV file: {e}", exc_info=True)

    def _process_row(self, row: Dict[str, Any]) -> None:
        """
        Processes a single CSV row into a Kafka message.

        Args:
            row (Dict[str, Any]): The CSV row to process.
        """
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

    def stop(self):
        """
        Stops the CSV source.
        """
        logger.info("Stopping CSV source...")
        self._running = False

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

__all__ = ["CSVSource"]
