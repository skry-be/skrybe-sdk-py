"""HTTP transport: request encoding, retries, timeouts and error mapping."""

from __future__ import annotations

import json
import logging
import random
import time
from typing import Any, Dict, Mapping, Optional, Tuple

import requests
import urllib3

from ._version import VERSION
from .errors import (
    ApiError,
    ConnectionError,
    SkrybeError,
    classify_prose,
    code_for_status,
    create_error,
    type_for_status,
)

logger = logging.getLogger("skrybe")

_RETRYABLE_STATUS = frozenset({429, 502, 503, 504})

Fields = Mapping[str, Any]


class Transport:
    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        timeout: float,
        max_retries: int,
        session: requests.Session,
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._max_retries = max_retries
        self._session = session

    def text(self, path: str, body: Optional[Fields] = None, *, retryable: bool = False) -> str:
        """Perform a request and return the body as text.

        Legacy endpoints answer HTTP 200 with a prose error, so a 2xx here is
        not proof of success: recognised prose errors are raised, and anything
        else is handed back for the caller to parse.

        ``retryable`` opts in to retrying. Off by default because most endpoints
        create or send something and none take an idempotency key: a 504 from a
        send that actually landed would send twice on retry. A dropped
        connection cannot be told apart from a response never seen, so only
        reads set it.
        """
        status, text = self._send("POST", path, body or {}, encoding="form", anonymous=False, retryable=retryable)
        if not 200 <= status < 300:
            raise _error_from_response(status, text)
        prose = classify_prose(text, status)
        if prose is not None:
            raise prose
        return text

    def json(
        self,
        path: str,
        body: Optional[Fields] = None,
        *,
        method: str = "POST",
        encoding: str = "form",
        anonymous: bool = False,
        retryable: bool = False,
    ) -> Dict[str, Any]:
        """Perform a request against one of the endpoints that returns real JSON."""
        status, text = self._send(method, path, body or {}, encoding=encoding, anonymous=anonymous, retryable=retryable)
        if not 200 <= status < 300:
            raise _error_from_response(status, text)
        try:
            parsed = json.loads(text)
        except ValueError:
            parsed = None
        if not isinstance(parsed, dict):
            raise ApiError(
                "malformed_response",
                "The API returned a response that was not valid JSON.",
                status=status,
                raw=text,
            )
        return parsed

    def _send(
        self,
        method: str,
        path: str,
        body: Fields,
        *,
        encoding: str,
        anonymous: bool,
        retryable: bool,
    ) -> Tuple[int, str]:
        target = f"{self._base_url}/{path.lstrip('/')}"

        fields: Dict[str, str] = {k: _field(v) for k, v in body.items() if v is not None}
        if not anonymous:
            fields["api_key"] = self._api_key

        headers = {"User-Agent": f"skrybe-sdk-py/{VERSION}"}
        kwargs: Dict[str, Any] = {}
        if method == "GET":
            kwargs["params"] = fields
        elif encoding == "json":
            headers["Content-Type"] = "application/json"
            kwargs["data"] = json.dumps(fields, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        else:
            headers["Content-Type"] = "application/x-www-form-urlencoded"
            kwargs["data"] = fields

        attempts = self._max_retries + 1 if retryable else 1
        last_error: Optional[BaseException] = None
        for attempt in range(1, attempts + 1):
            started = time.monotonic()
            try:
                response = self._session.request(
                    method,
                    target,
                    headers=headers,
                    timeout=self._timeout,
                    # A redirect would replay the API key to wherever it points.
                    allow_redirects=False,
                    **kwargs,
                )
            except requests.ConnectionError as exc:
                if _is_timeout(exc):
                    # Logged without the body: it carries the API key.
                    logger.warning("Skrybe API request timed out: %s %s", method, path)
                    raise ConnectionError(
                        "timeout", f"Request to {target} timed out after {self._timeout:g}s."
                    ) from exc
                logger.warning("Skrybe API request failed: %s %s: %s", method, path, type(exc).__name__)
                last_error = exc
                if attempt < attempts:
                    time.sleep(_backoff(attempt, None))
                    continue
                break
            except requests.Timeout as exc:
                logger.warning("Skrybe API request timed out: %s %s", method, path)
                raise ConnectionError(
                    "timeout", f"Request to {target} timed out after {self._timeout:g}s."
                ) from exc
            except requests.RequestException as exc:
                raise ConnectionError("network_error", f"Could not reach {self._base_url}: {exc}") from exc

            status = response.status_code
            # Decoded as UTF-8 whatever the headers say: several endpoints send
            # no Content-Type, and requests would otherwise guess.
            text = response.content.decode("utf-8", errors="replace")
            logger.debug(
                "Skrybe API request: %s %s -> %s in %dms",
                method,
                path,
                status,
                round((time.monotonic() - started) * 1000),
            )
            if status in _RETRYABLE_STATUS and attempt < attempts:
                time.sleep(_backoff(attempt, response.headers.get("Retry-After")))
                continue
            return status, text

        error = ConnectionError(
            "network_error",
            f"Could not reach {self._base_url}: {last_error if last_error is not None else 'unknown error'}",
        )
        raise error from last_error


def _is_timeout(exc: BaseException) -> bool:
    """A connect or read timeout, including one hit while reading the body,
    which requests reports as a plain ConnectionError."""
    if isinstance(exc, requests.Timeout):
        return True
    cause = exc.args[0] if exc.args else None
    return isinstance(cause, urllib3.exceptions.ReadTimeoutError)


def _field(value: Any) -> str:
    if isinstance(value, bool):
        return "1" if value else "0"
    return str(value)


def _error_from_response(status: int, text: str) -> SkrybeError:
    """Build an error from a non-2xx response.

    The JSON endpoints use ``{ok:false,error:...}`` (api/emails/send.php) or
    ``{status:"error",message:...}`` (api/emails/send-transactional.php).
    """
    message = text.strip()
    try:
        parsed = json.loads(text)
    except ValueError:
        parsed = None  # Not JSON: the prose body is already the best message we have.
    if isinstance(parsed, dict):
        extracted = parsed.get("error")
        if extracted is None:
            extracted = parsed.get("message")
        if isinstance(extracted, str) and extracted != "":
            message = extracted
    if message == "":
        message = f"HTTP {status} from the Skrybe API."
    return create_error(type_for_status(status), code_for_status(status), message, status=status, raw=text)


def _backoff(attempt: int, retry_after: Optional[str]) -> float:
    """Seconds to wait: Retry-After when present, else exponential backoff with jitter."""
    if retry_after is not None:
        value = retry_after.strip()
        if value.isdigit() and value.isascii():
            return min(int(value), 30)
    return 0.5 * 2.0 ** (attempt - 1) + random.random() * 0.25
