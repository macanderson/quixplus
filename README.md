# Quixplus

This project contains custom data sources for streaming data to QuixStreams using:
- **WebSocket**: Streams data from WebSocket endpoints.
- **CSV**: Streams data from CSV files.
- **HTTP**: Polls data from HTTP APIs at scheduled intervals.

Each source is designed to integrate with [QuixStreams](https://quix.ai/) for real-time data streaming in Python applications.

## Table of Contents
- [Quixplus](#quixplus)
  - [Table of Contents](#table-of-contents)
  - [Getting Started](#getting-started)
  - [Environment Setup](#environment-setup)
  - [Data Sources](#data-sources)
    - [WebSocket Source](#websocket-source)
    - [CSV Source](#csv-source)
    - [HTTP Source](#http-source)
  - [Usage](#usage)
    - [WebSocket Source Example](#websocket-source-example)
    - [CSV Source Example](#csv-source-example)
    - [HTTP Source Example](#http-source-example)
  - [Contributing](#contributing)
  - [License](#license)

## Getting Started

This project requires:
- Python 3.8 or higher
- [QuixStreams](https://github.com/quixio/quix-streams) library
- Access to your data sources (WebSocket endpoints, HTTP APIs, or CSV files)

## Environment Setup

**Clone this repository:**
   ```bash
   git clone https://github.com/your-username/your-repo.git
   cd your-repo
   ```

**Install the dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

**Set up your environment variables:**

To use the application factory method, you need to set up your environment variables.

   ```bash
   export BOOTSTRAP_SERVERS=<your-bootstrap-servers>
   export SASL_USERNAME=<your-username>
   export SASL_PASSWORD=<your-password>
   export SASL_MECHANISM=<your-sasl-mechanism>
   export SECURITY_PROTOCOL=<your-security-protocol>
   ```
## Data Sources

### WebSocket Source

The WebSocketSource class connects to a WebSocket endpoint, receives data, applies optional transformations, and streams it to QuixStreams.

**Key Features:**

- Connects to WebSocket URLs.
- Validates and transforms incoming messages.
- Sends data to a specified Kafka topic.

### CSV Source

The CSVSource class reads data from a CSV file, transforms each row, and streams it to QuixStreams.

**Key Features:**

- Reads from CSV files with configurable delimiters.
- Extracts each row as a JSON object, using column headers as keys.
- Supports configurable keys for Kafka messages and value serialization.

### HTTP Source

The AIOHTTPSource class polls an HTTP API endpoint at specified intervals, validates the data, and streams it to QuixStreams.

**Key Features:**

- Asynchronous polling with configurable intervals.
- Flexible authentication (Bearer token, Basic, or custom headers).
- Supports configurable JSON path extraction for Kafka keys and values.

**Installation:**

**Install from PyPI:**
   ```bash
   pip install quixplus
   ```
**Add your environment variables to the .env file.**

## Usage

### WebSocket Source Example

To use the WebSocket source, initialize it with the necessary configurations:

```python
from quixstreams import Application
from custom_sources.websocket_source import WebSocketSource

app = Application(broker_address="your_kafka_broker")
ws_source = WebSocketSource(
    topic="your_topic",
    ws_url="wss://your_websocket_endpoint",
    auth_payload={"api_key": "your_key"},
    subscribe_payload={"action": "subscribe", "params": "A.*"}
)
sdf = app.dataframe(source=ws_source)
sdf.print()
app.run()
```

### CSV Source Example

To use the CSV source, provide the path to your CSV file and specify the columns for Kafka keys:

```python
from quixstreams import Application
from custom_sources.csv_source import CSVSource

app = Application(broker_address="your_kafka_broker")
csv_source = CSVSource(
    topic="your_topic",
    csv_path="path/to/your/csv/file.csv",
    key_columns=["column1", "column2"]
)
sdf = app.dataframe(source=csv_source)
sdf.print()
app.run()
```

### HTTP Source Example

To use the HTTP source, set the URL and polling interval:

```python
from quixstreams import Application
from custom_sources.http_source import AIOHTTPSource

app = Application(broker_address="your_kafka_broker")
http_source = AIOHTTPSource(
    url="https://your-api-endpoint",
    poll_interval=10,
    auth_type="bearer",
    auth_credentials="your_bearer_token",
    key_json_path="$.data.id",
    value_json_path="$.data"
)
sdf = app.dataframe(source=http_source)
sdf.print()
app.run()
```

## Contributing

We welcome contributions! Please read our CONTRIBUTING.md for guidelines on contributing to this project.

## License

This project is licensed under the MIT License.
