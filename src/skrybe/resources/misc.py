from __future__ import annotations

from typing import List, cast

from .._parse import parse_numbered_object
from .._transport import Transport
from ..errors import is_prose_empty
from ..types import Brand


class Brands:
    def __init__(self, transport: Transport) -> None:
        self._transport = transport

    def list(self) -> List[Brand]:
        """The key's own brand: a brand key gets exactly one row.

        Empty, not an error, when there is none.
        """
        body = self._transport.text("api/brands/get-brands.php", retryable=True)
        if is_prose_empty(body):
            return []
        return cast(List[Brand], parse_numbered_object(body, "brand"))


class Stats:
    def __init__(self, transport: Transport) -> None:
        self._transport = transport

    def total_emails_sent(self) -> int:
        """Emails sent across the whole installation, not a per-brand figure.

        Counts campaigns, autoresponders and transactional email. Public (sent
        without the API key) and cached for 5 minutes.
        """
        data = self._transport.json("api/stats/emails-sent.php", method="GET", anonymous=True, retryable=True)
        total = data.get("total_emails_sent")
        return int(total) if total is not None else 0
