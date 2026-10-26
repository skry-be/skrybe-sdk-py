from __future__ import annotations

import json
from typing import Any, Iterable, Mapping, Optional, Union

from .._transport import Transport
from ..errors import InvalidRequestError, require_params
from ..types import SendEmailResult, SendTransactionalResult, Tracking
from ._shared import Ids, as_list, join_ids

#: send.php refuses more than this, and says so with a 400.
MAX_RECIPIENTS = 250


def _encode(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


class Emails:
    def __init__(self, transport: Transport) -> None:
        self._transport = transport

    def send(
        self,
        *,
        from_name: str,
        from_email: str,
        reply_to: str,
        subject: str,
        html_text: str,
        plain_text: Optional[str] = None,
        to: Union[str, Iterable[str], None] = None,
        recipient_variables: Optional[Mapping[str, Mapping[str, Any]]] = None,
        list_ids: Optional[Ids] = None,
        query_string: Optional[str] = None,
        track_opens: Optional[Tracking] = None,
        track_clicks: Optional[Tracking] = None,
        schedule_date_time: Optional[str] = None,
        schedule_timezone: Optional[str] = None,
    ) -> SendEmailResult:
        """A bulk send to addresses or lists, via ``api/emails/send.php``.

        It creates a campaign behind the scenes; the subject doubles as its
        title. Not retried.

        Args:
            to: at most 250 addresses. Without ``list_ids`` these are added to
                a new list.
            recipient_variables: per-recipient values keyed by address,
                referenced in the body as ``[recipient.first]``.
            list_ids: encrypted list ids, as ``lists.list()`` returns them.
            track_opens, track_clicks: 0 off, 1 on, 2 anonymous.
            schedule_date_time: e.g. ``"June 15, 2027 6:05pm"``;
                ``schedule_timezone`` e.g. ``"Africa/Lagos"``, defaulting to
                the brand's.

        Returns:
            ``{"message": ..., "campaign_id": ...}``.
        """
        require_params(
            {"from_name": from_name, "from_email": from_email, "reply_to": reply_to, "subject": subject, "html_text": html_text},
            ["from_name", "from_email", "reply_to", "subject", "html_text"],
        )
        recipients = as_list(to)
        lists = join_ids(list_ids)
        if not recipients and lists is None:
            raise InvalidRequestError(
                "recipients_missing", "Nothing to send to.", hint="Pass `to` addresses, or `list_ids`."
            )
        # Checked here so a 251-address send fails before it is transmitted.
        if len(recipients) > MAX_RECIPIENTS:
            raise InvalidRequestError(
                "too_many_recipients",
                f"{len(recipients)} recipients is more than the {MAX_RECIPIENTS} this endpoint accepts.",
                hint="Split the send, or put the addresses on a list and pass `list_ids`.",
            )

        data = self._transport.json(
            "api/emails/send.php",
            {
                "from_name": from_name,
                "from_email": from_email,
                "reply_to": reply_to,
                "subject": subject,
                "html_text": html_text,
                "plain_text": plain_text,
                # Both go over the wire as JSON strings inside a form body.
                "to": _encode(recipients) if recipients else None,
                "recipient-variables": _encode(dict(recipient_variables)) if recipient_variables else None,
                "list_ids": lists,
                "query_string": query_string,
                "track_opens": track_opens,
                "track_clicks": track_clicks,
                "schedule_date_time": schedule_date_time,
                "schedule_timezone": schedule_timezone,
            },
        )
        message = data.get("message")
        inner = data.get("data")
        campaign_id = inner.get("campaign_id") if isinstance(inner, dict) else None
        return {
            "message": message if isinstance(message, str) else "Sent.",
            "campaign_id": str(campaign_id) if campaign_id is not None else None,
        }

    def send_transactional(
        self,
        *,
        to_email: str,
        subject: str,
        html_body: Optional[str] = None,
        plain_body: Optional[str] = None,
        from_name: Optional[str] = None,
        from_email: Optional[str] = None,
        reply_to: Optional[str] = None,
    ) -> SendTransactionalResult:
        """One email, delivered immediately with nothing queued.

        For OTPs, password resets and receipts, via
        ``api/emails/send-transactional.php``. At least one of ``html_body``
        and ``plain_body`` is required; the sender fields fall back to the
        brand's configured values. Not retried.

        Returns:
            ``{"message": ..., "message_id": ...}``.
        """
        require_params({"to_email": to_email, "subject": subject}, ["to_email", "subject"])
        if not html_body and not plain_body:
            raise InvalidRequestError(
                "body_missing", "A message body is required.", hint="Pass `html_body`, `plain_body`, or both."
            )

        # The one endpoint that reads php://input: a form post gets "Invalid JSON payload."
        data = self._transport.json(
            "api/emails/send-transactional.php",
            {
                "to_email": to_email,
                "subject": subject,
                "html_body": html_body,
                "plain_body": plain_body,
                "from_name": from_name,
                "from_email": from_email,
                "reply_to": reply_to,
            },
            encoding="json",
        )
        message = data.get("message")
        message_id = data.get("message_id")
        return {
            "message": message if isinstance(message, str) else "Email sent successfully.",
            "message_id": str(message_id) if message_id is not None else None,
        }
