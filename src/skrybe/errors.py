"""Exceptions, and the rules that turn the API's answers into them.

The Skrybe API answers most failures with HTTP 200 and a prose sentence. Only
``api/emails/send.php``, ``api/emails/send-transactional.php`` and
``api/stats/emails-sent.php`` use real status codes. Everything here exists to
turn that into something code can branch on: every failure is a
:class:`SkrybeError` with a stable ``code``, and its subclass says what kind of
failure it is.

Kept in step with ``@skrybe/sdk``'s ``src/errors.ts``, ``skrybe/sdk-php``'s
``src/Internal/Errors.php`` and skrybe-cli's ``src/api/errors.ts``.
"""

from __future__ import annotations

import re
from typing import Dict, List, Mapping, NamedTuple, Optional, Sequence, Tuple, Type

__all__ = [
    "SkrybeError",
    "AuthenticationError",
    "InvalidRequestError",
    "RateLimitError",
    "ConnectionError",
    "ApiError",
]


class SkrybeError(Exception):
    """Every failure the SDK reports.

    Attributes:
        code: stable machine-readable slug, e.g. ``list_not_found``.
        type: ``authentication``, ``invalid_request``, ``rate_limit``,
            ``connection`` or ``api``.
        hint: what to do about it, when known.
        status: HTTP status of the response, when there was one.
        raw: raw response body, kept for debugging odd endpoints.
    """

    type: str = "api"

    def __init__(
        self,
        code: str,
        message: str,
        *,
        hint: Optional[str] = None,
        status: Optional[int] = None,
        raw: Optional[str] = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.hint = hint
        self.status = status
        self.raw = raw

    def __repr__(self) -> str:
        return f"{type(self).__name__}(code={self.code!r}, message={self.message!r})"


class AuthenticationError(SkrybeError):
    """The API key is missing or wrong."""

    type = "authentication"


class InvalidRequestError(SkrybeError):
    """The request itself is wrong; retrying it unchanged will fail again."""

    type = "invalid_request"


class RateLimitError(SkrybeError):
    """A quota or rate limit was hit."""

    type = "rate_limit"


class ConnectionError(SkrybeError):  # noqa: A001 - mirrors the other SDKs' name
    """The API could not be reached, or did not answer in time (``code == "timeout"``).

    Shadows the builtin of the same name inside this module only; import it as
    ``skrybe.ConnectionError`` or alias it.
    """

    type = "connection"


class ApiError(SkrybeError):
    """Anything else the API refused or got wrong."""

    type = "api"


_BY_TYPE: Dict[str, Type[SkrybeError]] = {
    "authentication": AuthenticationError,
    "invalid_request": InvalidRequestError,
    "rate_limit": RateLimitError,
    "connection": ConnectionError,
    "api": ApiError,
}


def create_error(
    type_: str,
    code: str,
    message: str,
    *,
    hint: Optional[str] = None,
    status: Optional[int] = None,
    raw: Optional[str] = None,
) -> SkrybeError:
    """Build the subclass for an error type; unknown types become :class:`ApiError`."""
    cls = _BY_TYPE.get(type_, ApiError)
    return cls(code, message, hint=hint, status=status, raw=raw)


_WHITESPACE = re.compile(r"\s+")


def excerpt(body: str, limit: int = 200) -> str:
    """Render an unexpected body for a message.

    Whitespace is collapsed so a multi-line PHP warning stays on one line, and
    the text truncated so a stray HTML page does not swamp a log. The whole body
    stays on :attr:`SkrybeError.raw`.
    """
    flat = _WHITESPACE.sub(" ", body).strip()
    if flat == "":
        return "(an empty response)"
    return f"{flat[:limit]}…" if len(flat) > limit else flat


class _Rule(NamedTuple):
    code: str
    type: str
    hint: Optional[str] = None


_LIST_IDS_HINT = "Call skrybe.lists.list() to see the IDs available to this API key."
_UNDER_REVIEW_HINT = (
    "Sending is paused while the brand is reviewed for a high bounce rate. Contact Skrybe support."
)
_DOMAIN_HINT = "Verify the From domain for this brand in the Skrybe dashboard."

# Prose returned by the legacy endpoints, keyed by the lowercased trimmed body.
_PROSE: Mapping[str, _Rule] = {
    # Authentication
    "api key not passed": _Rule("api_key_missing", "authentication"),
    "invalid api key": _Rule(
        "invalid_api_key",
        "authentication",
        "Generate a key in the Skrybe dashboard under Settings. "
        "Keys are cleared for every login of a brand placed under review.",
    ),
    # Request shape
    "no data passed": _Rule("no_data_passed", "invalid_request"),
    "some fields are missing.": _Rule("missing_fields", "invalid_request"),
    # Brands and lists
    "brand id not passed": _Rule("brand_id_missing", "invalid_request"),
    # Also the answer to the install's main account key, which no brand is tied to.
    "brand does not exist": _Rule(
        "brand_not_found",
        "api",
        "Use an API key from a brand login; the main account key is not tied to a brand.",
    ),
    "list does not exist": _Rule("list_not_found", "api", _LIST_IDS_HINT),
    "invalid list id.": _Rule("list_not_found", "api", _LIST_IDS_HINT),
    # Also what the server produces from an id it cannot decrypt, so this is
    # the answer to a malformed id as much as to a missing one.
    "list id not passed": _Rule(
        "list_id_invalid",
        "invalid_request",
        "A list ID is the encrypted value skrybe.lists.list() returns, "
        "not the number in the dashboard URL.",
    ),
    # Autoresponders
    "autoresponder id not passed": _Rule("autoresponder_id_missing", "invalid_request"),
    "autoresponder does not exist": _Rule("autoresponder_not_found", "api"),
    "email id not passed": _Rule("email_id_missing", "invalid_request"),
    "autoresponder email does not exist": _Rule("autoresponder_email_not_found", "api"),
    "autoresponder name not passed": _Rule("autoresponder_name_missing", "invalid_request"),
    "type must be drip, annually or on_date": _Rule("invalid_autoresponder_type", "invalid_request"),
    "list already has a drip autoresponder": _Rule(
        "drip_exists",
        "api",
        "A list can have one drip autoresponder. Add emails to the existing one.",
    ),
    "custom_field not passed": _Rule(
        "custom_field_missing",
        "invalid_request",
        "annually and on_date autoresponders send on a Date custom field of the list.",
    ),
    "field is not a date field": _Rule("field_not_date", "invalid_request"),
    "field already has an autoresponder": _Rule("field_has_autoresponder", "api"),
    "subject not passed": _Rule("subject_missing", "invalid_request"),
    "a drip email cannot go before signup": _Rule("invalid_when", "invalid_request"),
    "when must be immediately, or a delay such as +3 days": _Rule("invalid_when", "invalid_request"),
    "when must be on, or an offset such as +9 hours or -1 days": _Rule("invalid_when", "invalid_request"),
    # Templates
    "template id not passed": _Rule("template_id_missing", "invalid_request"),
    "template does not exist": _Rule("template_not_found", "api"),
    "template name not passed": _Rule("template_name_missing", "invalid_request"),
    "template name cannot be empty": _Rule("template_name_missing", "invalid_request"),
    "html not passed": _Rule("html_missing", "invalid_request"),
    "editor must be html or dragdrop": _Rule("invalid_editor", "invalid_request"),
    # List management
    "list name not passed": _Rule("list_name_missing", "invalid_request"),
    "list name is too long": _Rule(
        "list_name_too_long", "invalid_request", "A list name can be at most 100 characters."
    ),
    "opt_in must be single or double": _Rule("invalid_opt_in", "invalid_request"),
    "nothing to update": _Rule("nothing_to_update", "invalid_request", "Pass at least one field to change."),
    "list is used by a scheduled or sending campaign": _Rule(
        "list_in_use",
        "api",
        "Unschedule the campaign, or wait for it to finish sending, then delete the list.",
    ),
    # Custom fields
    "field name not passed": _Rule("field_name_missing", "invalid_request"),
    "invalid field name": _Rule(
        "invalid_field_name", "invalid_request", 'Up to 100 characters, without : % [ ] , " < or >.'
    ),
    "name and email are built-in fields": _Rule("reserved_field_name", "invalid_request"),
    "type must be text or date": _Rule("invalid_field_type", "invalid_request"),
    "field already exists": _Rule("field_exists", "api", "Field names are case-insensitive."),
    "field does not exist": _Rule("field_not_found", "api"),
    "field is used by an autoresponder": _Rule(
        "field_in_use", "api", "Change the autoresponder in the Skrybe dashboard first."
    ),
    "field is used by a segment": _Rule(
        "field_in_use", "api", "Remove it from the segment in the Skrybe dashboard first."
    ),
    "list was changed by another request. try again.": _Rule("conflict", "api"),
    # Campaigns
    "campaign id not passed": _Rule("campaign_id_missing", "invalid_request"),
    "campaign does not exist": _Rule("campaign_not_found", "api"),
    "invalid status": _Rule("invalid_status", "invalid_request"),
    "invalid page": _Rule("invalid_page", "invalid_request"),
    "invalid limit": _Rule("invalid_limit", "invalid_request"),
    "invalid type": _Rule("invalid_type", "invalid_request"),
    # Sending a campaign
    "list or segment id(s) not passed": _Rule(
        "recipients_missing", "invalid_request", "Pass at least one list or segment ID."
    ),
    "one or more list ids are invalid": _Rule("list_not_found", "api", _LIST_IDS_HINT),
    "one or more segment ids are invalid": _Rule("segment_not_found", "api"),
    "campaign has already been sent": _Rule(
        "campaign_not_draft",
        "api",
        "It has already started sending, so it can no longer be sent, scheduled or edited.",
    ),
    "campaign is scheduled": _Rule(
        "campaign_scheduled", "api", "Unschedule it first, or leave it to send at its scheduled time."
    ),
    "campaign is not scheduled": _Rule("campaign_not_scheduled", "api"),
    # Editing and deleting campaigns
    "campaign is sending": _Rule(
        "campaign_sending", "api", "Stop it in the Skrybe dashboard first, or wait for it to finish."
    ),
    "subject cannot be empty": _Rule("subject_empty", "invalid_request"),
    "html cannot be empty": _Rule("html_empty", "invalid_request"),
    "invalid from_email": _Rule("invalid_from_email", "invalid_request"),
    "invalid reply_to": _Rule("invalid_reply_to", "invalid_request"),
    "track_opens and track_clicks must be 0, 1 or 2": _Rule(
        "invalid_tracking", "invalid_request", "0 off, 1 on, 2 anonymous."
    ),
    "campaign was changed by another request. try again.": _Rule("conflict", "api"),
    # Scheduling
    "schedule_date_time not passed": _Rule("schedule_missing", "invalid_request"),
    "schedule_date_time is invalid": _Rule(
        "invalid_schedule",
        "invalid_request",
        'Use a date and time such as "2027-06-15 18:05" or "June 15, 2027 6:05pm".',
    ),
    "schedule_date_time is in the past": _Rule(
        "schedule_in_past",
        "invalid_request",
        "The time is read in the timezone given, or the account's timezone if none is.",
    ),
    "schedule_timezone is invalid": _Rule(
        "invalid_timezone", "invalid_request", "Use an IANA name such as Africa/Lagos or America/New_York."
    ),
    # Test sends
    "email addresses not passed": _Rule("emails_missing", "invalid_request"),
    "too many email addresses": _Rule(
        "too_many_emails", "invalid_request", "A test send goes to at most 5 addresses."
    ),
    "quota exceeded. please upgrade your plan.": _Rule("quota_exceeded", "rate_limit"),
    "no active subscribers to send to": _Rule(
        "no_recipients",
        "api",
        "Every subscriber on those lists is unsubscribed, bounced, unconfirmed or excluded.",
    ),
    # Subscribers
    "subscriber does not exist": _Rule("subscriber_not_found", "api"),
    "email does not exist in list": _Rule("subscriber_not_found", "api"),
    "email not passed": _Rule("email_missing", "invalid_request"),
    "email address not passed": _Rule("email_missing", "invalid_request"),
    "invalid email address.": _Rule("invalid_email", "invalid_request"),
    "bounced email address.": _Rule("bounced_email", "api"),
    "email is suppressed.": _Rule("suppressed_email", "api"),
    # unsubscribe's wording for an address that is not on the list.
    "email does not exist.": _Rule("subscriber_not_found", "api"),
    "ip address is invalid.": _Rule("invalid_ip_address", "invalid_request"),
    "country must be a valid 2 letter country code": _Rule(
        "invalid_country", "invalid_request", "Use a two-letter ISO 3166-1 code, e.g. NG."
    ),
    "referrer is not a valid url": _Rule("invalid_referrer", "invalid_request"),
    "consent not given.": _Rule(
        "consent_not_given", "invalid_request", "The list requires GDPR consent; pass gdpr=True."
    ),
    "failed recaptcha test.": _Rule(
        "recaptcha_failed",
        "api",
        "The list has reCAPTCHA enabled on its subscribe form, which an API call cannot satisfy.",
    ),
    # Sending
    "unauthorised from email domain": _Rule(
        "unauthorised_from_domain",
        "api",
        "The From domain must be verified for this brand, or listed in its allowed domains.",
    ),
}

# Prose with a variable part, matched by pattern after the exact table.
_PROSE_PATTERNS: Sequence[Tuple["re.Pattern[str]", _Rule]] = [
    (re.compile(r"^error: this campaign would exceed"), _Rule("quota_exceeded", "rate_limit")),
    (re.compile(r"^account under review:"), _Rule("account_under_review", "api", _UNDER_REVIEW_HINT)),
    (re.compile(r"^brand is under review"), _Rule("account_under_review", "api", _UNDER_REVIEW_HINT)),
    (re.compile(r"^a field is too long"), _Rule("field_too_long", "invalid_request")),
    (
        re.compile(r"^test send rate limit reached"),
        _Rule(
            "rate_limited",
            "rate_limit",
            "Test sends are limited to 20 an hour per brand, shared with the Skrybe dashboard.",
        ),
    ),
    (re.compile(r"^domain not verified in ses"), _Rule("domain_not_verified", "api", _DOMAIN_HINT)),
    (re.compile(r'^domain ".*" is not verified'), _Rule("domain_not_verified", "api", _DOMAIN_HINT)),
]

# Bodies that mean "nothing to return" rather than a failure: these endpoints
# answer with prose instead of an empty object when the brand has no rows.
_PROSE_EMPTY = frozenset({"no lists found", "no brands found", "no campaigns found"})

# Bodies that mean success even though they are bare prose.
_PROSE_OK = frozenset({"1", "true", "already subscribed."})


def _key(body: str) -> str:
    return body.strip().lower()


def is_prose_empty(body: str) -> bool:
    return _key(body) in _PROSE_EMPTY


def is_prose_success(body: str) -> bool:
    return _key(body) in _PROSE_OK


def classify_prose(body: str, status: Optional[int] = None) -> Optional[SkrybeError]:
    """Classify a legacy plain-text body.

    Returns ``None`` when the body is not a recognised error, which callers
    should treat as data.
    """
    trimmed = body.strip()
    key = trimmed.lower()

    rule = _PROSE.get(key)
    if rule is None:
        for pattern, candidate in _PROSE_PATTERNS:
            if pattern.search(key):
                rule = candidate
                break
    if rule is not None:
        return create_error(rule.type, rule.code, trimmed, hint=rule.hint, status=status, raw=body)

    # A family of "Unable to ..." server-side failures not worth enumerating.
    if key.startswith("unable to"):
        return ApiError("operation_failed", trimmed, status=status, raw=body)

    return None


def type_for_status(status: int) -> str:
    """The error type for an HTTP status from one of the JSON endpoints."""
    if status in (401, 403):
        return "authentication"
    if status in (402, 429):
        return "rate_limit"
    if status in (400, 405, 422):
        return "invalid_request"
    return "api"


_CODE_FOR_STATUS = {
    400: "invalid_request",
    401: "unauthenticated",
    402: "quota_exceeded",
    403: "forbidden",
    404: "not_found",
    405: "method_not_allowed",
    429: "rate_limited",
}


def code_for_status(status: int) -> str:
    if status in _CODE_FOR_STATUS:
        return _CODE_FOR_STATUS[status]
    return "server_error" if status >= 500 else "api_error"


def unexpected_response(operation: str, body: str) -> ApiError:
    """A body that is neither a known success nor a known failure."""
    return ApiError("unexpected_response", f"Unexpected response from {operation}: {excerpt(body)}", raw=body)


def require_params(params: Mapping[str, object], names: Sequence[str]) -> None:
    """Refuse a required parameter passed as ``None`` or ``""`` before anything is sent."""
    missing: List[str] = [n for n in names if params.get(n) is None or params.get(n) == ""]
    if missing:
        plural = "s" if len(missing) > 1 else ""
        raise InvalidRequestError(
            "missing_params", f"Missing required parameter{plural}: {', '.join(missing)}."
        )
