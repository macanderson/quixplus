# Quixplus HttpSource for Quixstreams

The `HttpSource` is a custom polling source for Quixstreams that allows you to connect to an HTTP API, process responses dynamically, and produce messages to Kafka. It supports features like:

- **Dynamic JSON root handling** for APIs that return arrays or encapsulated objects.
- **Duplicate prevention** with a configurable TTL-based deduplication mechanism.
- **Custom headers and timestamps** via user-defined callable functions.
- **Authentication options** including Bearer tokens, Basic Auth, and custom headers.
- **Flexible scheduling** with polling intervals or cron expressions.

## Features

1. **Authentication**
   - No Auth
   - Bearer Token
   - Basic Auth
   - Custom Headers
2. **Duplicate Prevention**
   - Configurable TTL-based deduplication.
3. **Dynamic JSON Root Handling**
   - Supports extracting data from lists or single objects, e.g., `{ "data": [ {...}, {...} ] }`.
4. **Custom Headers and Timestamp Callables**
   - Add custom Kafka headers or timestamps per message.

## Installation

To use this custom source, install the necessary dependencies:

```bash
pip install aiohttp apscheduler jsonpath-ng cachetools quixstreams
```

## Example Usage

### 1. No Authentication, Polling Every 10 Seconds

```python
from quixplus import HttpSource

source = HttpSource(
    name="ExampleSource",
    url="https://api.example.com/data",
    poll_interval=10,
    root_json_path="$.data",
    key_json_path="$.id",
)
app.add_source(source)
```

### 2. Basic Authentication, Scheduled Using Cron

```python
from quixplus import HttpSource, AuthType

source = HttpSource(
    name="AuthSource",
    url="https://api.secure.com/data",
    auth_type=AuthType.BASIC,
    auth_credentials=("username", "password"),
    schedule_cron="*/5 * * * *",  # Every 5 minutes
    root_json_path="$.data",
    key_json_path="$.id",
)
app.add_source(source)
```

### 3. Deduplication with TTL of 5 Minutes

```python
from quixplus import HttpSource

source = HttpSource(
    name="DedupSource",
    url="https://api.example.com/data",
    deduplicate=True,
    deduplication_ttl=300,  # 5 minutes
    root_json_path="$.data",
    key_json_path="$.unique_id",
)
app.add_source(source)
```

### 4. Bearer Token Authentication

```python
from quixplus import HttpSource, AuthType

source = HttpSource(
    name="BearerSource",
    url="https://api.example.com/protected-data",
    auth_type=AuthType.BEARER,
    auth_credentials="your-bearer-token",
    poll_interval=15,
    root_json_path="$.data",
    key_json_path="$.id",
)
app.add_source(source)
```

### 5. Custom Headers and Timestamp

```python
from my_custom_sources import HttpSource

def custom_headers(source, record):
    return {"X-Custom-Header": f"Value-{record.get('id')}"}

def custom_timestamp(source, record):
    return int(record.get("timestamp") * 1000)  # Convert seconds to ms

source = HttpSource(
    name="CustomSource",
    url="https://api.example.com/data",
    custom_headers_func=custom_headers,
    timestamp_func=custom_timestamp,
    root_json_path="$.data",
    key_json_path="$.id",
)
app.add_source(source)
```

## Parameters

| Parameter           | Type                                        | Default        | Description                                                       |
| :------------------ | :------------------------------------------ | :------------- | :---------------------------------------------------------------- |
| name                | str                                         | Required       | The name of the source.                                           |
| url                 | str                                         | Required       | The API endpoint to poll.                                         |
| poll_interval       | float                                       | 5.0            | The polling interval in seconds. Ignored if `schedule_cron` is set. |
| auth_type           | AuthType                                    | None           | Authentication type (`BEARER`, `BASIC`, or `CUSTOM`).             |
| auth_credentials    | Union[str, Tuple[str, str], Dict[str, str]] | None           | Authentication credentials for the specified `auth_type`.         |
| root_json_path      | str                                         | None           | JSONPath for the root object(s).                                  |
| key_json_path       | str                                         | None           | JSONPath for extracting the message key.                         |
| schedule_cron       | str                                         | None           | Cron expression for scheduling. Ignored if `poll_interval` is set. |
| shutdown_timeout    | float                                       | 10             | Timeout for a graceful shutdown.                                  |
| validate            | Callable[[Dict], bool]                     | lambda x: True | Function to validate records before producing them.               |
| transform           | Callable[[Dict], Dict]                     | lambda x: x    | Function to transform records.                                    |
| deduplicate         | bool                                        | True           | Whether to enable deduplication.                                  |
| deduplication_ttl   | int                                         | 300            | Time-to-live for deduplication keys in seconds.                   |
| custom_headers_func | Callable[[Source, Dict], Dict[str, str]]    | None           | Function to generate custom Kafka headers.                        |
| timestamp_func      | Callable[[Source, Dict], int]              | None           | Function to generate custom timestamps in milliseconds.           |


## JSONPath Examples

#### Root Path for Arrays:

`$.data` extracts the data field: `{ "data": [ {...}, {...} ] }`.

#### Key Extraction:

`$.id` extracts the id field: `{ "id": "123", "name": "Example" }`.

## Contributing
Feel free to contribute improvements or report issues by creating a pull request or opening an issue in the repository.

## License
This project is licensed under the MIT License.