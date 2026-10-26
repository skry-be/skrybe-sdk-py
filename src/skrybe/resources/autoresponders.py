from __future__ import annotations

from typing import List, Optional, cast

from .._parse import parse_json_object
from .._transport import Transport
from ..errors import require_params
from ..types import (
    Autoresponder,
    AutoresponderEmail,
    AutoresponderEmailStats,
    AutoresponderType,
    AutoresponderWithEmails,
    Tracking,
)
from ._shared import flag


class Autoresponders:
    """``drip`` sends each email a set time after someone joins; ``annually``
    and ``on_date`` send on a Date custom field, every year or once."""

    def __init__(self, transport: Transport) -> None:
        self._transport = transport

    def list(self, *, list_id: Optional[str] = None) -> List[Autoresponder]:
        """The brand's autoresponders, or one list's."""
        body = self._transport.text(
            "api/autoresponders/get-autoresponders.php", {"list_id": list_id}, retryable=True
        )
        return cast(List[Autoresponder], parse_json_object(body, "autoresponders").get("autoresponders") or [])

    def get(self, autoresponder_id: int) -> AutoresponderWithEmails:
        """One autoresponder with its emails, under ``email_list``."""
        body = self._transport.text(
            "api/autoresponders/get-autoresponder-emails.php",
            {"autoresponder_id": autoresponder_id},
            retryable=True,
        )
        return cast(AutoresponderWithEmails, parse_json_object(body, "autoresponder"))

    def email_stats(self, email_id: int) -> AutoresponderEmailStats:
        body = self._transport.text(
            "api/autoresponders/autoresponder-stats.php", {"email_id": email_id}, retryable=True
        )
        return cast(AutoresponderEmailStats, parse_json_object(body, "autoresponder email stats"))

    def create(
        self,
        *,
        name: str,
        type: AutoresponderType,  # noqa: A002 - the API's name
        list_id: str,
        custom_field: Optional[str] = None,
    ) -> Autoresponder:
        """Create an autoresponder with no emails; add them with :meth:`create_email`.

        A list can have one drip autoresponder. ``custom_field`` is required for
        ``annually`` and ``on_date``: a Date custom field of the list, one
        autoresponder per field. Not retried.
        """
        require_params({"name": name, "type": type, "list_id": list_id}, ["name", "type", "list_id"])
        body = self._transport.text(
            "api/autoresponders/create-autoresponder.php",
            {"name": name, "type": type, "list_id": list_id, "custom_field": custom_field},
        )
        return cast(Autoresponder, parse_json_object(body, "autoresponder"))

    def create_email(
        self,
        autoresponder_id: int,
        *,
        subject: str,
        html_text: str,
        plain_text: Optional[str] = None,
        preheader: Optional[str] = None,
        when: Optional[str] = None,
        from_name: Optional[str] = None,
        from_email: Optional[str] = None,
        reply_to: Optional[str] = None,
        query_string: Optional[str] = None,
        track_opens: Optional[Tracking] = None,
        track_clicks: Optional[Tracking] = None,
        enabled: bool = False,
    ) -> AutoresponderEmail:
        """Add an email to an autoresponder. Not retried: a repeat would add it twice.

        Args:
            when: for a drip, ``"immediately"`` (the default) or a delay such
                as ``"+3 days"``; for annually and on_date, ``"on"`` (the
                default, the date itself) or an offset such as ``"+9 hours"``
                or ``"-1 days"``. Units: minute, hour, day, week, month.
            from_name, from_email, reply_to: each falls back to the brand's sender.
            enabled: emails are created switched off, as the dashboard creates
                them, unless this is True.
        """
        require_params({"subject": subject, "html_text": html_text}, ["subject", "html_text"])
        body = self._transport.text(
            "api/autoresponders/create-autoresponder-email.php",
            {
                "autoresponder_id": autoresponder_id,
                "subject": subject,
                "html_text": html_text,
                "plain_text": plain_text,
                "preheader": preheader,
                "when": when,
                "from_name": from_name,
                "from_email": from_email,
                "reply_to": reply_to,
                "query_string": query_string,
                "track_opens": track_opens,
                "track_clicks": track_clicks,
                "enabled": flag(enabled),
            },
        )
        return cast(AutoresponderEmail, parse_json_object(body, "autoresponder email"))
