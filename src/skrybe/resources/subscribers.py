from __future__ import annotations

from typing import Dict, List, Mapping, Optional, cast

from .._parse import parse_json_object
from .._transport import Transport
from ..errors import is_prose_success, require_params, unexpected_response
from ..types import SubscribeOutcome, Subscriber, SubscribersPage, SubscriberStatus

#: Every subscriber is in exactly one of these; ``active`` is who a campaign sends to.
SUBSCRIBER_STATUSES = ("active", "unconfirmed", "unsubscribed", "bounced", "complained")
#: The largest page get-subscribers.php serves.
MAX_SUBSCRIBERS_PAGE = 1000


class Subscribers:
    def __init__(self, transport: Transport) -> None:
        self._transport = transport

    def subscribe(
        self,
        *,
        list_id: str,
        email: str,
        name: Optional[str] = None,
        country: Optional[str] = None,
        ip_address: Optional[str] = None,
        referrer: Optional[str] = None,
        gdpr: bool = False,
        silent: bool = False,
        fields: Optional[Mapping[str, str]] = None,
    ) -> SubscribeOutcome:
        """Add an address to a list.

        Posting one that is already there updates its name and custom fields,
        and returns ``"already_subscribed"`` rather than raising, so re-running
        an import is safe. Not retried.

        Args:
            list_id: the encrypted list id, as ``lists.list()`` returns it.
            country: two-letter ISO 3166-1 code, e.g. ``"NG"``.
            gdpr: record GDPR consent for an EU signup.
            silent: add to a double opt-in list as single opt-in, skipping
                confirmation.
            fields: custom fields keyed by the name the list shows, e.g.
                ``{"Birthday": "1990-12-10"}``. Spaces are taken out of the
                names before sending, as the server matches on.

        Returns:
            ``"subscribed"`` or ``"already_subscribed"``.
        """
        require_params({"list_id": list_id, "email": email}, ["list_id", "email"])

        body: Dict[str, Optional[str]] = {}
        for field_name, value in (fields or {}).items():
            body[str(field_name).replace(" ", "")] = value

        # Written after the custom fields so the documented names win a collision.
        body["email"] = email
        body["list"] = list_id
        # Switches subscribe.php from rendering an HTML page to answering in plain text.
        body["boolean"] = "true"
        if name is not None:
            body["name"] = name
        if country is not None:
            body["country"] = country
        if ip_address is not None:
            body["ipaddress"] = ip_address
        if referrer is not None:
            body["referrer"] = referrer
        if gdpr:
            body["gdpr"] = "true"
        if silent:
            body["silent"] = "true"

        # At the install root, not under api/.
        text = self._transport.text("subscribe", body)
        if text.strip().lower() == "already subscribed.":
            return "already_subscribed"
        if is_prose_success(text):
            return "subscribed"
        raise unexpected_response("subscribe", text)

    def unsubscribe(self, list_id: str, email: str) -> None:
        """Mark the address unsubscribed from the list."""
        text = self._transport.text("unsubscribe", {"email": email, "list": list_id, "boolean": "true"})
        if not is_prose_success(text):
            raise unexpected_response("unsubscribe", text)

    def delete(self, list_id: str, email: str) -> None:
        """Remove the subscriber outright, rather than marking it unsubscribed."""
        text = self._transport.text("api/subscribers/delete.php", {"list_id": list_id, "email": email})
        if not is_prose_success(text):
            raise unexpected_response("delete", text)

    def status(self, list_id: str, email: str) -> str:
        """One of Subscribed, Unsubscribed, Unconfirmed, Bounced, Soft bounced or Complained.

        Returned as given, so a status added server-side surfaces rather than
        being rejected.
        """
        text = self._transport.text(
            "api/subscribers/subscription-status.php", {"email": email, "list_id": list_id}, retryable=True
        )
        status = text.strip()
        if status == "":
            raise unexpected_response("subscription-status", text)
        return status

    def list(
        self,
        list_id: str,
        *,
        status: Optional[SubscriberStatus] = None,
        page: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> SubscribersPage:
        """One page of a list's subscribers, oldest first. ``limit`` is at most 1000."""
        body = self._transport.text(
            "api/subscribers/get-subscribers.php",
            {"list_id": list_id, "status": status, "page": page, "limit": limit},
            retryable=True,
        )
        return cast(SubscribersPage, parse_json_object(body, "subscribers page"))

    def list_all(self, list_id: str, *, status: Optional[SubscriberStatus] = None) -> List[Subscriber]:
        """Every page, at the largest page size.

        Oldest first, so someone joining mid-way lands on a later page instead
        of shifting the ones already read.
        """
        rows: List[Subscriber] = []
        page = 1
        while True:
            result = self.list(list_id, status=status, page=page, limit=MAX_SUBSCRIBERS_PAGE)
            batch = result.get("subscribers") or []
            rows.extend(batch)
            if len(batch) < MAX_SUBSCRIBERS_PAGE:
                return rows
            page += 1
