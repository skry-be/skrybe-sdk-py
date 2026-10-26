from __future__ import annotations

import json
from typing import Any, Dict, Iterable, List, Optional, Union, cast

from .._parse import parse_json_object, parse_numbered_records
from .._transport import Transport
from ..errors import ApiError, excerpt, is_prose_empty, require_params
from ..types import (
    ActivityType,
    Campaign,
    CampaignActivity,
    CampaignActivityPage,
    CampaignDetail,
    CampaignStats,
    CampaignStatus,
    CreateCampaignResult,
    DeleteCampaignResult,
    ScheduleCampaignResult,
    SendCampaignResult,
    TestSendResult,
    Tracking,
    UnscheduleCampaignResult,
)
from ._shared import Ids, as_list, flag, join_ids

#: As the brand's campaign list labels them.
CAMPAIGN_STATUSES = ("draft", "scheduled", "preparing", "sending", "sent", "paused")
ACTIVITY_TYPES = ("opens", "clicks", "bounces", "complaints", "unsubscribes")
#: The largest page get-campaigns.php serves.
MAX_CAMPAIGNS_PAGE = 100
#: The largest page get-activity.php serves.
MAX_ACTIVITY_PAGE = 1000
#: test-send.php refuses more than this many addresses per request.
MAX_TEST_EMAILS = 5


def _recipient_fields(
    list_ids: Optional[Ids],
    segment_ids: Optional[Ids],
    exclude_list_ids: Optional[Ids],
    exclude_segment_ids: Optional[Ids],
    dry_run: bool,
) -> Dict[str, Any]:
    return {
        "list_ids": join_ids(list_ids),
        "segment_ids": join_ids(segment_ids),
        "exclude_list_ids": join_ids(exclude_list_ids),
        # send.php and schedule.php read exclude_segment_ids (create.php differs).
        "exclude_segment_ids": join_ids(exclude_segment_ids),
        "dry_run": flag(dry_run),
    }


class Campaigns:
    def __init__(self, transport: Transport) -> None:
        self._transport = transport

    def create(
        self,
        *,
        from_name: str,
        from_email: str,
        reply_to: str,
        title: str,
        subject: str,
        html_text: str,
        plain_text: Optional[str] = None,
        list_ids: Optional[Ids] = None,
        segment_ids: Optional[Ids] = None,
        exclude_list_ids: Optional[Ids] = None,
        exclude_segment_ids: Optional[Ids] = None,
        query_string: Optional[str] = None,
        track_opens: Optional[Tracking] = None,
        track_clicks: Optional[Tracking] = None,
        send: bool = False,
        schedule_date_time: Optional[str] = None,
        schedule_timezone: Optional[str] = None,
    ) -> CreateCampaignResult:
        """Create a draft, and optionally send or schedule it in the same call.

        ``list_ids``/``segment_ids`` are needed only to send or schedule. To send
        a draft that already exists, see :meth:`send`. Not retried.

        Returns:
            ``{"outcome": "created" | "sending" | "scheduled", "campaign_id": ...}``;
            ``campaign_id`` is only known for a plain create, and is ``None``
            otherwise.
        """
        require_params(
            {
                "from_name": from_name,
                "from_email": from_email,
                "reply_to": reply_to,
                "title": title,
                "subject": subject,
                "html_text": html_text,
            },
            ["from_name", "from_email", "reply_to", "title", "subject", "html_text"],
        )
        text = self._transport.text(
            "api/campaigns/create.php",
            {
                "from_name": from_name,
                "from_email": from_email,
                "reply_to": reply_to,
                "title": title,
                "subject": subject,
                "html_text": html_text,
                "plain_text": plain_text,
                "list_ids": join_ids(list_ids),
                "segment_ids": join_ids(segment_ids),
                "exclude_list_ids": join_ids(exclude_list_ids),
                # Sic: create.php reads exclude_segments_ids.
                "exclude_segments_ids": join_ids(exclude_segment_ids),
                "query_string": query_string,
                "track_opens": track_opens,
                "track_clicks": track_clicks,
                "send_campaign": flag(send),
                "schedule_date_time": schedule_date_time,
                "schedule_timezone": schedule_timezone,
                # Asks for {"status": ..., "campaign_id": ...} instead of bare prose.
                "json": 1,
            },
        )
        trimmed = text.strip()

        if trimmed == "Campaign scheduled":
            return {"outcome": "scheduled", "campaign_id": None}
        if trimmed == "Campaign created and now sending":
            return {"outcome": "sending", "campaign_id": None}
        if trimmed == "Campaign created":
            return {"outcome": "created", "campaign_id": None}

        # The json=1 shape, built by hand server-side, so parsed leniently.
        if trimmed.startswith("{"):
            try:
                parsed = json.loads(trimmed)
            except ValueError:
                parsed = None  # Reported below with the body intact.
            if isinstance(parsed, dict):
                status = parsed.get("status")
                if isinstance(status, str) and status.startswith("Campaign created"):
                    campaign_id = parsed.get("campaign_id")
                    return {
                        "outcome": "created",
                        "campaign_id": str(campaign_id) if campaign_id is not None else None,
                    }

        raise ApiError(
            "unexpected_response", f"Unexpected response from campaigns/create: {excerpt(trimmed)}", raw=text
        )

    def list(
        self,
        *,
        page: Optional[int] = None,
        limit: Optional[int] = None,
        status: Optional[CampaignStatus] = None,
    ) -> List[Campaign]:
        """One page, newest first. ``page`` is 1-based, ``limit`` at most 100.

        An empty page is an empty list, not an error.
        """
        body = self._transport.text(
            "api/campaigns/get-campaigns.php",
            {"page": page, "limit": limit, "status": status},
            retryable=True,
        )
        if is_prose_empty(body):
            return []
        return cast(List[Campaign], parse_numbered_records(body, "campaign"))

    def list_all(self, *, status: Optional[CampaignStatus] = None) -> List[Campaign]:
        """Every page, fetched in order at the largest page size."""
        rows: List[Campaign] = []
        page = 1
        while True:
            batch = self.list(page=page, limit=MAX_CAMPAIGNS_PAGE, status=status)
            rows.extend(batch)
            if len(batch) < MAX_CAMPAIGNS_PAGE:
                return rows
            page += 1

    def get(self, campaign_id: int, *, include_content: bool = False) -> CampaignDetail:
        """One campaign; ``html_text`` and ``plain_text`` only with ``include_content``."""
        body = self._transport.text(
            "api/campaigns/get-campaign.php",
            {"campaign_id": campaign_id, "include_content": "yes" if include_content else None},
            retryable=True,
        )
        return cast(CampaignDetail, parse_json_object(body, "campaign"))

    def stats(self, campaign_id: int) -> CampaignStats:
        body = self._transport.text("api/campaigns/stats.php", {"campaign_id": campaign_id}, retryable=True)
        return cast(CampaignStats, parse_json_object(body, "campaign stats"))

    def send(
        self,
        campaign_id: int,
        *,
        list_ids: Optional[Ids] = None,
        segment_ids: Optional[Ids] = None,
        exclude_list_ids: Optional[Ids] = None,
        exclude_segment_ids: Optional[Ids] = None,
        dry_run: bool = False,
    ) -> SendCampaignResult:
        """Send an existing draft to lists and/or segments.

        ``dry_run=True`` runs every check and counts the recipients, but sends
        nothing. send.php only ever claims a draft, so a repeat after a lost
        response answers "Campaign has already been sent" rather than sending
        twice. It is still not retried: that answer would turn a success into a
        reported failure.
        """
        body = self._transport.text(
            "api/campaigns/send.php",
            {
                "campaign_id": campaign_id,
                **_recipient_fields(list_ids, segment_ids, exclude_list_ids, exclude_segment_ids, dry_run),
            },
        )
        return cast(SendCampaignResult, parse_json_object(body, "send result"))

    def test_send(self, campaign_id: int, emails: Union[str, Iterable[str]]) -> TestSendResult:
        """Send the campaign as a test to up to 5 addresses.

        Each request counts against a per-brand limit shared with the dashboard
        (20 an hour), so it is never retried.
        """
        body = self._transport.text(
            "api/campaigns/test-send.php",
            {"campaign_id": campaign_id, "emails": ",".join(as_list(emails))},
        )
        return cast(TestSendResult, parse_json_object(body, "test send result"))

    def schedule(
        self,
        campaign_id: int,
        *,
        at: str,
        timezone: Optional[str] = None,
        list_ids: Optional[Ids] = None,
        segment_ids: Optional[Ids] = None,
        exclude_list_ids: Optional[Ids] = None,
        exclude_segment_ids: Optional[Ids] = None,
        dry_run: bool = False,
    ) -> ScheduleCampaignResult:
        """Schedule a draft, or move a scheduled campaign.

        ``at`` is anything PHP's strtotime() reads, e.g. ``"2027-06-15 18:05"``;
        ``timezone`` e.g. ``"Africa/Lagos"``, defaulting to the account's. The
        recipients are reserved against the quota now and handed back by
        :meth:`unschedule`.
        """
        require_params({"at": at}, ["at"])
        body = self._transport.text(
            "api/campaigns/schedule.php",
            {
                "campaign_id": campaign_id,
                **_recipient_fields(list_ids, segment_ids, exclude_list_ids, exclude_segment_ids, dry_run),
                "schedule_date_time": at,
                "schedule_timezone": timezone,
            },
        )
        return cast(ScheduleCampaignResult, parse_json_object(body, "schedule result"))

    def unschedule(self, campaign_id: int) -> UnscheduleCampaignResult:
        """Back to a draft, with its quota reservation refunded."""
        body = self._transport.text("api/campaigns/unschedule.php", {"campaign_id": campaign_id})
        return cast(UnscheduleCampaignResult, parse_json_object(body, "unschedule result"))

    def update(
        self,
        campaign_id: int,
        *,
        title: Optional[str] = None,
        subject: Optional[str] = None,
        preheader: Optional[str] = None,
        from_name: Optional[str] = None,
        from_email: Optional[str] = None,
        reply_to: Optional[str] = None,
        html_text: Optional[str] = None,
        plain_text: Optional[str] = None,
        query_string: Optional[str] = None,
        track_opens: Optional[Tracking] = None,
        track_clicks: Optional[Tracking] = None,
    ) -> CampaignDetail:
        """Edit a draft or scheduled campaign; only the fields given change.

        Returns the campaign as :meth:`get` would.
        """
        body = self._transport.text(
            "api/campaigns/update-campaign.php",
            {
                "campaign_id": campaign_id,
                "title": title,
                "subject": subject,
                "preheader": preheader,
                "from_name": from_name,
                "from_email": from_email,
                "reply_to": reply_to,
                "html_text": html_text,
                "plain_text": plain_text,
                "query_string": query_string,
                "track_opens": track_opens,
                "track_clicks": track_clicks,
            },
        )
        return cast(CampaignDetail, parse_json_object(body, "campaign"))

    def duplicate(self, campaign_id: int, *, title: Optional[str] = None) -> CampaignDetail:
        """A new draft copied from the campaign, in the same brand."""
        body = self._transport.text(
            "api/campaigns/duplicate-campaign.php", {"campaign_id": campaign_id, "title": title}
        )
        return cast(CampaignDetail, parse_json_object(body, "campaign"))

    def delete(self, campaign_id: int) -> DeleteCampaignResult:
        """Delete the campaign with its links and attachments; a sent one loses its report.

        Refused while the campaign is preparing or sending.
        """
        body = self._transport.text("api/campaigns/delete-campaign.php", {"campaign_id": campaign_id})
        return cast(DeleteCampaignResult, parse_json_object(body, "delete result"))

    def activity(
        self,
        campaign_id: int,
        *,
        type: Optional[ActivityType] = None,  # noqa: A002 - the API's name
        page: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> CampaignActivityPage:
        """A page of who opened, clicked, bounced, complained or unsubscribed.

        Opens and clicks are in the order subscribers first did them. ``limit``
        is at most 1000.
        """
        body = self._transport.text(
            "api/campaigns/get-activity.php",
            {"campaign_id": campaign_id, "type": type, "page": page, "limit": limit},
            retryable=True,
        )
        return cast(CampaignActivityPage, parse_json_object(body, "campaign activity"))

    def activity_all(self, campaign_id: int, type: ActivityType) -> List[CampaignActivity]:  # noqa: A002
        """Every page of one activity type, at the largest page size."""
        rows: List[CampaignActivity] = []
        page = 1
        while True:
            result = self.activity(campaign_id, type=type, page=page, limit=MAX_ACTIVITY_PAGE)
            batch = result.get("activity") or []
            rows.extend(batch)
            if not batch or page * MAX_ACTIVITY_PAGE >= int(result.get("total") or 0):
                return rows
            page += 1
