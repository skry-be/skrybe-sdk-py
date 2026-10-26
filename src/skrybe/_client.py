from __future__ import annotations

from typing import Optional

import requests

from ._transport import Transport
from .errors import InvalidRequestError
from .resources import Autoresponders, Brands, Campaigns, Emails, Lists, Stats, Subscribers, Templates

DEFAULT_BASE_URL = "https://dashboard.skry.be"


class Skrybe:
    """The Skrybe API client.

    >>> skrybe = Skrybe(api_key="...")
    >>> lists = skrybe.lists.list()

    Args:
        api_key: a brand's API key, from Settings in the Skrybe dashboard.
            Keep it server-side.
        base_url: defaults to https://dashboard.skry.be.
        timeout: seconds per attempt, default 30.
        max_retries: extra attempts for reads after a dropped connection or a
            429/502/503/504, default 2. Writes are never retried: the API has
            no idempotency keys, so a retried send could go out twice.
        session: a ``requests.Session`` to send through, e.g. one with
            ``proxies`` set or ``verify`` pointing at a corporate CA bundle.
            The SDK makes its own when none is given. Note that requests also
            honours the ``HTTPS_PROXY`` and ``REQUESTS_CA_BUNDLE`` environment
            variables.
    """

    emails: Emails
    campaigns: Campaigns
    lists: Lists
    subscribers: Subscribers
    templates: Templates
    autoresponders: Autoresponders
    brands: Brands
    stats: Stats

    def __init__(
        self,
        api_key: str,
        *,
        base_url: Optional[str] = None,
        timeout: float = 30,
        max_retries: int = 2,
        session: Optional[requests.Session] = None,
    ) -> None:
        if not api_key:
            raise InvalidRequestError(
                "api_key_missing",
                "An api_key is required.",
                hint="Generate one in the Skrybe dashboard under Settings.",
            )

        self._base_url = (base_url or DEFAULT_BASE_URL).rstrip("/")
        self._session = session if session is not None else requests.Session()
        self._owns_session = session is None
        transport = Transport(
            api_key=api_key,
            base_url=self._base_url,
            timeout=timeout,
            max_retries=max(0, int(max_retries)),
            session=self._session,
        )

        self.emails = Emails(transport)
        self.campaigns = Campaigns(transport)
        self.lists = Lists(transport)
        self.subscribers = Subscribers(transport)
        self.templates = Templates(transport)
        self.autoresponders = Autoresponders(transport)
        self.brands = Brands(transport)
        self.stats = Stats(transport)

    def close(self) -> None:
        """Close the HTTP session the client made. A session passed in is left open."""
        if self._owns_session:
            self._session.close()

    def __enter__(self) -> "Skrybe":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def __repr__(self) -> str:
        # Never the key.
        return f"<Skrybe {self._base_url}>"
