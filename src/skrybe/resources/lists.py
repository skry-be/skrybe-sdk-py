from __future__ import annotations

import re
from typing import List, Optional, cast

from .._parse import parse_json_object, parse_numbered_object
from .._transport import Transport
from ..errors import ApiError, excerpt, is_prose_empty
from ..types import CustomFieldType, DeleteListResult, ListDetail, ListSummary, OptIn

_COUNT = re.compile(r"[0-9]+")


class Lists:
    def __init__(self, transport: Transport) -> None:
        self._transport = transport

    def list(self, *, include_hidden: bool = False) -> List[ListSummary]:
        """The brand's lists as ``[{"id", "name"}]``. An empty brand is an empty list, not an error.

        Ids are encrypted strings, not the number in the dashboard URL: pass
        them back exactly as given.
        """
        body = self._transport.text(
            "api/lists/get-lists.php",
            {"include_hidden": "yes" if include_hidden else "no"},
            retryable=True,
        )
        if is_prose_empty(body):
            return []
        return cast(List[ListSummary], parse_numbered_object(body, "list"))

    def get(self, list_id: str) -> ListDetail:
        """One list with its opt-in, subscriber counts and custom fields."""
        body = self._transport.text("api/lists/get-list.php", {"list_id": list_id}, retryable=True)
        return cast(ListDetail, parse_json_object(body, "list"))

    def create(self, name: str, *, opt_in: Optional[OptIn] = None) -> ListDetail:
        """Not retried: a repeat after a lost response would create a second list."""
        body = self._transport.text("api/lists/create.php", {"name": name, "opt_in": opt_in})
        return cast(ListDetail, parse_json_object(body, "list"))

    def update(self, list_id: str, *, name: Optional[str] = None, opt_in: Optional[OptIn] = None) -> ListDetail:
        """Rename the list or change its opt-in; only the fields given change."""
        body = self._transport.text(
            "api/lists/update-list.php", {"list_id": list_id, "name": name, "opt_in": opt_in}
        )
        return cast(ListDetail, parse_json_object(body, "list"))

    def delete(self, list_id: str) -> DeleteListResult:
        """Delete the list with its subscribers, segments, autoresponders and rules.

        Refused while a scheduled or sending campaign is going to it.
        """
        body = self._transport.text("api/lists/delete.php", {"list_id": list_id})
        return cast(DeleteListResult, parse_json_object(body, "delete result"))

    def active_subscriber_count(self, list_id: str) -> int:
        """Subscribers a campaign to this list would reach.

        Anything but a bare integer is a failure and is raised, never reported
        as 0: "this list is empty" is the one wrong answer a caller cannot
        detect.
        """
        body = self._transport.text(
            "api/subscribers/active-subscriber-count.php", {"list_id": list_id}, retryable=True
        )
        trimmed = body.strip()
        if not _COUNT.fullmatch(trimmed):
            raise ApiError(
                "malformed_response",
                f"Expected a subscriber count for list {list_id}, got: {excerpt(trimmed)}",
                raw=body,
            )
        return int(trimmed)

    def add_custom_field(
        self,
        list_id: str,
        name: str,
        *,
        type: Optional[CustomFieldType] = None,  # noqa: A002 - the API's name
    ) -> ListDetail:
        """Add a field (``text`` by default); every subscriber gets an empty value for it.

        Returns the list with its fields.
        """
        body = self._transport.text(
            "api/lists/add-custom-field.php", {"list_id": list_id, "name": name, "type": type}
        )
        return cast(ListDetail, parse_json_object(body, "list"))

    def rename_custom_field(self, list_id: str, name: str, new_name: str) -> ListDetail:
        """Rename a field, keeping subscribers' values.

        The autoresponders and segment conditions that use it follow; tags
        already in campaigns keep the old name.
        """
        body = self._transport.text(
            "api/lists/rename-custom-field.php", {"list_id": list_id, "name": name, "new_name": new_name}
        )
        return cast(ListDetail, parse_json_object(body, "list"))

    def delete_custom_field(self, list_id: str, name: str) -> ListDetail:
        """Delete a field and every subscriber's value for it.

        Refused while an autoresponder or segment uses it.
        """
        body = self._transport.text("api/lists/delete-custom-field.php", {"list_id": list_id, "name": name})
        return cast(ListDetail, parse_json_object(body, "list"))
