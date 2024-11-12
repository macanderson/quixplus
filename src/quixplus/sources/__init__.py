"""
Quixplus is a Python library for building sources for Quix Streams.
This module contains all the custom sources available in Quixplus.

**Classes:**
    - CSVSource: A CSV source for Quixstreams that reads data from a CSV file and produces messages.
    - HttpSource: An HTTP source for Quixstreams that reads data from an HTTP endpoint and produces messages.
    - WebsocketSource: A WebSocket source for Quixstreams that reads data from a WebSocket endpoint and produces messages.

**Generic Example:**

```python
import quixstreams as qx
from quixplus import HttpSource

# initialize the source (http, websocket, csv, etc.)
my_source = NameOfSource(...)
# initialize the output topic
my_topic = qx.models.Topic(...)

my_app = qx.Application()

# add the source to the application
my_app.add_source(source=my_source, topic=my_topic)

# run the application
my_app.run()
```
"""
from .csv import CSVSource
from .http import HttpSource
from .tornado_websocket import TornadoWebsocketSource
from .websocket import WebsocketSource

__all__ = [
    "CSVSource",
    "HttpSource",
    "WebsocketSource",
    "TornadoWebsocketSource",
]
