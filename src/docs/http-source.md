# HttpSource for Quixstreams

The `HttpSource` is a custom polling source for Quixstreams that allows you to connect to an HTTP API, process responses dynamically, and produce messages to Kafka. It supports features like:

- **Dynamic JSON root handling** for APIs that return arrays or encapsulated objects.
- **Duplicate prevention** with a configurable TTL-based deduplication mechanism.
- **Custom headers and timestamps** via user-defined callable functions.
- **Authentication options** including Bearer tokens, Basic Auth, and custom headers.
- **Flexible scheduling** with polling intervals or cron expressions.

---

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

---

## Installation

To use this custom source, install the necessary dependencies:

```bash
pip install aiohttp apscheduler jsonpath-ng cachetools quixstreams

Example Usage

1. No Authentication, Polling Every 10 Seconds

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

2. Basic Authentication, Scheduled Using Cron

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

3. Deduplication with TTL of 5 Minutes

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

4. Bearer Token Authentication

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

5. Custom Headers and Timestamp

```python
from quixplus import HttpSource

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

