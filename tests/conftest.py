"""A real HTTP server for the tests to talk to.

The point of testing against a real socket rather than a mocked session is
that the legacy API's quirks are wire-level (a 200 carrying a prose failure, a
form body, a missing Content-Type) and a mock that returns whatever the client
asked for would assert nothing about them.
"""

from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Callable, Dict, Iterator, List, Optional, Sequence, Union
from urllib.parse import parse_qsl, urlsplit

import pytest

from skrybe import Skrybe

KEY = "test-api-key"


@dataclass
class Received:
    method: str
    path: str
    content_type: Optional[str]
    # Form fields, already decoded; JSON bodies and query strings too.
    fields: Dict[str, str]
    raw_body: str
    headers: Dict[str, str]


@dataclass
class Reply:
    body: str = ""
    status: int = 200
    headers: Dict[str, str] = field(default_factory=dict)
    # Hold the response for this long, for exercising the client timeout.
    delay: float = 0.0


Replies = Union[Sequence[Union[Reply, str]], Callable[[Received, int], Reply]]


class Stub:
    def __init__(self, replies: Replies) -> None:
        self.received: List[Received] = []
        self._replies = replies
        stub = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args: object) -> None:  # quiet
                pass

            def _handle(self) -> None:
                length = int(self.headers.get("Content-Length") or 0)
                raw = self.rfile.read(length).decode("utf-8") if length else ""
                url = urlsplit(self.path)
                content_type = self.headers.get("Content-Type")
                fields: Dict[str, str] = {}
                if content_type and "application/x-www-form-urlencoded" in content_type:
                    fields.update(parse_qsl(raw, keep_blank_values=True))
                elif content_type and "application/json" in content_type and raw:
                    fields.update(json.loads(raw))
                fields.update(parse_qsl(url.query, keep_blank_values=True))

                entry = Received(
                    method=self.command,
                    path=url.path,
                    content_type=content_type,
                    fields=fields,
                    raw_body=raw,
                    headers={k: v for k, v in self.headers.items()},
                )
                index = len(stub.received)
                stub.received.append(entry)
                reply = stub._pick(entry, index)
                if reply.delay:
                    time.sleep(reply.delay)
                payload = reply.body.encode("utf-8")
                try:
                    self.send_response(reply.status)
                    for k, v in reply.headers.items():
                        self.send_header(k, v)
                    self.send_header("Content-Length", str(len(payload)))
                    self.end_headers()
                    self.wfile.write(payload)
                except (BrokenPipeError, ConnectionResetError):
                    pass

            do_GET = _handle
            do_POST = _handle

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self._server.daemon_threads = True
        self._thread = threading.Thread(target=self._server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
        self._thread.start()
        host, port = self._server.server_address[:2]
        self.url = f"http://{host}:{port}"

    def _pick(self, entry: Received, index: int) -> Reply:
        if callable(self._replies):
            return self._replies(entry, index)
        if not self._replies:
            return Reply()
        reply = self._replies[min(index, len(self._replies) - 1)]
        return Reply(body=reply) if isinstance(reply, str) else reply

    def close(self) -> None:
        self._server.shutdown()
        self._server.server_close()

    def sent(self) -> Dict[str, str]:
        """The fields of the only request, less the api key every request carries."""
        assert len(self.received) == 1
        fields = dict(self.received[0].fields)
        assert fields.pop("api_key") == KEY
        return fields


@pytest.fixture
def stub() -> Iterator[Callable[..., Stub]]:
    """``stub(replies)`` starts a server answering ``replies`` in order, repeating the last."""
    started: List[Stub] = []

    def start(replies: Replies) -> Stub:
        s = Stub(replies)
        started.append(s)
        return s

    yield start
    for s in started:
        s.close()


@pytest.fixture
def setup(stub: Callable[..., Stub]) -> Callable[..., "tuple[Stub, Skrybe]"]:
    """``setup(replies, **options)`` returns a stub and a client pointed at it."""

    def make(replies: Replies, **options: object) -> "tuple[Stub, Skrybe]":
        s = stub(replies)
        return s, Skrybe(KEY, base_url=s.url, **options)  # type: ignore[arg-type]

    return make


def php_numbered_payload(prefix: str, rows: Sequence[Dict[str, str]]) -> str:
    """The exact payload get-lists.php and get-brands.php emit: string-concatenated,
    unescaped, with their real indentation. Tests that built the payload with
    json.dumps would never see the bug the parser exists for."""
    output = "{"
    for i, row in enumerate(rows):
        output += f'"{prefix}{i + 1}":\n\t\t{{\n\t\t\t"id": "{row["id"]}",\n\t\t\t"name": "{row["name"]}"\n\t\t}},'
    return output[:-1] + "}"
