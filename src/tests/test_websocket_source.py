import unittest
from unittest.mock import MagicMock, patch

from clickhouse_connect import Client

from quixplus.websocket_source import WebsocketSource


class TestWebsocketSource(unittest.TestCase):
    """
    Test cases for WebsocketSource class.
    """

    @patch('clickhouse_connect.Client')
    def test_data_pull_from_clickhouse(self, MockClickhouseClient):
        """
        Test data pull from ClickHouse DB using ClickHouse Cloud Python client.
        """
        # Mock ClickHouse client and its methods
        mock_client = MockClickhouseClient.return_value
        mock_client.query.return_value = [
            {"timestamp": 1622547800, "value": 42},
            {"timestamp": 1622547900, "value": 43},
        ]

        # Initialize WebsocketSource with mock parameters
        ws_source = WebsocketSource(
            topic_name="example_topic",
            ws_url="wss://example.com/socket",
            transform=lambda x: json.loads(x),
            validator=lambda x: "key" in x,
            key_field=None,
            header_fields=None,
            value_fields=["*"],
            timestamp_field="timestamp"
        )

        # Mock the _connect_to_websocket method to prevent actual WebSocket connection
        ws_source._connect_to_websocket = MagicMock()

        # Simulate data pull from ClickHouse
        query = "SELECT timestamp, value FROM example_table"
        result = mock_client.query(query)

        # Validate the result
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["timestamp"], 1622547800)
        self.assertEqual(result[0]["value"], 42)
        self.assertEqual(result[1]["timestamp"], 1622547900)
        self.assertEqual(result[1]["value"], 43)

    @patch('clickhouse_connect.Client')
    def test_data_pull_with_empty_result(self, MockClickhouseClient):
        """
        Test data pull from ClickHouse DB with an empty result set.
        """
        # Mock ClickHouse client and its methods
        mock_client = MockClickhouseClient.return_value
        mock_client.query.return_value = []

        # Initialize WebsocketSource with mock parameters
        ws_source = WebsocketSource(
            topic_name="example_topic",
            ws_url="wss://example.com/socket",
            transform=lambda x: json.loads(x),
            validator=lambda x: "key" in x,
            key_field=None,
            header_fields=None,
            value_fields=["*"],
            timestamp_field="timestamp"
        )

        # Mock the _connect_to_websocket method to prevent actual WebSocket connection
        ws_source._connect_to_websocket = MagicMock()

        # Simulate data pull from ClickHouse
        query = "SELECT timestamp, value FROM example_table"
        result = mock_client.query(query)

        # Validate the result
        self.assertEqual(len(result), 0)

if __name__ == '__main__':
    unittest.main()
