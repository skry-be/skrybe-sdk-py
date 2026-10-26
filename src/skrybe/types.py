"""Shapes of the dicts the SDK returns.

Results are plain dicts shaped as the API's JSON, so their keys are the API's
snake_case names. These TypedDicts exist for editors and type checkers; nothing
validates responses against them at runtime, and a field the API adds later
simply appears in the dict.
"""

from __future__ import annotations

from typing import Dict, List, Literal, Optional, TypedDict, Union

# 0 off, 1 on, 2 anonymous.
Tracking = Literal[0, 1, 2]

CampaignStatus = Literal["draft", "scheduled", "preparing", "sending", "sent", "paused"]
ActivityType = Literal["opens", "clicks", "bounces", "complaints", "unsubscribes"]
SubscriberStatus = Literal["active", "unconfirmed", "unsubscribed", "bounced", "complained"]
SubscribeOutcome = Literal["subscribed", "already_subscribed"]
OptIn = Literal["single", "double"]
CustomFieldType = Literal["text", "date"]
TemplateEditor = Literal["html", "dragdrop"]
AutoresponderType = Literal["drip", "annually", "on_date"]


# --- emails ------------------------------------------------------------------


class SendEmailResult(TypedDict):
    message: str
    # The campaign the send created behind the scenes.
    campaign_id: Optional[str]


class SendTransactionalResult(TypedDict):
    message: str
    message_id: Optional[str]


# --- shared ------------------------------------------------------------------


class _Opens(TypedDict):
    total: int
    unique: int
    # A percentage of delivered (recipients less hard bounces).
    rate: float


class _Clicks(TypedDict):
    total: int
    unique: int
    # A percentage of recipients.
    rate: float


class _Bounces(TypedDict):
    hard: int
    soft: int


class _LinkStats(TypedDict):
    url: str
    clicks: int
    unique_clicks: int


class EngagementStats(TypedDict):
    """Opens, clicks, bounces and the rest, as campaign and autoresponder stats report them."""

    recipients: int
    opens: _Opens
    clicks: _Clicks
    bounces: _Bounces
    complaints: int
    unsubscribes: int
    links: List[_LinkStats]


# --- campaigns ---------------------------------------------------------------


class CreateCampaignResult(TypedDict):
    outcome: Literal["created", "sending", "scheduled"]
    # Only for a plain create: the sending and scheduling paths of create.php
    # answer with bare prose and no id.
    campaign_id: Optional[str]


class Campaign(TypedDict):
    """One row of ``campaigns.list()``."""

    id: int
    title: str
    subject: str
    status: CampaignStatus
    from_name: str
    from_email: str
    reply_to: str
    recipients: int
    to_send: int
    sent_at: Optional[int]  # Unix seconds.
    scheduled_at: Optional[int]  # Unix seconds, only while scheduled.
    timezone: Optional[str]
    source: str  # "ui", or "api" for campaigns created by emails.send().


class CampaignDetail(Campaign, total=False):
    preheader: str
    query_string: str
    track_opens: Tracking
    track_clicks: Tracking
    list_ids: List[str]  # Encrypted, like the ids lists.list() returns.
    exclude_list_ids: List[str]
    segment_ids: List[int]
    exclude_segment_ids: List[int]
    web_version: str
    html_text: str  # Only with include_content=True.
    plain_text: str


class CampaignStats(EngagementStats):
    id: int
    status: CampaignStatus


class SendCampaignResult(TypedDict):
    status: Literal["sending", "dry_run"]
    campaign_id: int
    # Unique active subscribers the campaign goes (or would go) to.
    recipients: int


class ScheduleCampaignResult(TypedDict):
    status: Literal["scheduled", "dry_run"]
    campaign_id: int
    recipients: int
    scheduled_at: int  # Unix seconds.
    timezone: str


class UnscheduleCampaignResult(TypedDict):
    status: Literal["draft"]
    campaign_id: int


class TestSendRecipientResult(TypedDict):
    email: str
    ok: bool
    error: Optional[str]


class TestSendResult(TypedDict):
    campaign_id: int
    results: List[TestSendRecipientResult]  # One per address, in the order sent.


class DeleteCampaignResult(TypedDict):
    campaign_id: int
    deleted: bool


class CampaignActivity(TypedDict, total=False):
    """One subscriber's part in a campaign.

    ``opens``/``country`` only for opens, ``clicks``/``links`` only for clicks.
    """

    email: str
    name: str
    list_id: str
    opens: int
    country: Optional[str]
    clicks: int
    links: List[str]


class CampaignActivityPage(TypedDict):
    campaign_id: int
    type: ActivityType
    page: int
    limit: int
    total: int  # Subscribers across all pages.
    activity: List[CampaignActivity]


# --- lists -------------------------------------------------------------------


class ListSummary(TypedDict):
    # An encrypted value, not the number in the dashboard URL. Pass it back
    # as given wherever a list id is wanted.
    id: str
    name: str


class CustomField(TypedDict):
    name: str  # As used in personalization tags: [Name,fallback=].
    type: Literal["Text", "Date"]


class SubscriberCounts(TypedDict):
    # Who a campaign goes to: confirmed, and not unsubscribed, bounced or complained.
    active: int
    unconfirmed: int
    unsubscribed: int
    bounced: int
    complained: int


class ListDetail(ListSummary):
    opt_in: OptIn
    subscribers: SubscriberCounts
    custom_fields: List[CustomField]  # In the order subscribers' values are stored.


class DeleteListResult(TypedDict):
    id: str
    deleted: bool


# --- subscribers -------------------------------------------------------------


class Subscriber(TypedDict):
    email: str
    name: str
    status: SubscriberStatus
    joined_at: Optional[int]  # Unix seconds.
    # By field name, in the list's order. Dates are YYYY-MM-DD; empty values are None.
    custom_fields: Dict[str, Optional[str]]


class SubscribersPage(TypedDict):
    list_id: str
    status: Optional[SubscriberStatus]
    page: int
    limit: int
    total: int  # Subscribers matching the status filter, across all pages.
    subscribers: List[Subscriber]


# --- templates ---------------------------------------------------------------


class Template(TypedDict, total=False):
    id: int
    name: str
    from_name: str
    from_email: str
    reply_to: str
    editor: TemplateEditor
    # Only from get() with include_content=True, and from create() and update().
    html_text: str
    plain_text: str


class DeleteTemplateResult(TypedDict):
    template_id: int
    deleted: bool


# --- autoresponders ----------------------------------------------------------


class Autoresponder(TypedDict):
    id: int
    name: str
    type: Union[AutoresponderType, Literal["unknown"]]
    list_id: str  # Encrypted, like the ids lists.list() returns.
    custom_field: Optional[str]  # The date field an annually or on_date autoresponder sends on.
    emails: int
    enabled_emails: int


class AutoresponderEmail(TypedDict):
    id: int
    autoresponder_id: int
    subject: str
    from_name: str
    from_email: str
    # As stored: "immediately", "+3 days", "-1 days", or "" for the date itself.
    when: str
    enabled: bool
    recipients: int
    created_at: Optional[int]  # Unix seconds.


class AutoresponderWithEmails(Autoresponder):
    email_list: List[AutoresponderEmail]


class AutoresponderEmailStats(EngagementStats):
    id: int
    autoresponder_id: int


# --- brands ------------------------------------------------------------------


class Brand(TypedDict):
    id: str
    name: str
