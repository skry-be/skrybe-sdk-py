# skrybe-sdk

The official Python SDK for the [Skrybe](https://skry.be) email marketing API.
It covers every brand-key endpoint: transactional and bulk email, the full
campaign lifecycle, lists and custom fields, subscribers, templates and
autoresponders.

- **Typed errors.** The API answers most failures with HTTP 200 and a sentence
  of prose. The SDK turns each one into a `SkrybeError` with a stable `code`, so
  you can branch on it.
- **One dependency:** [`requests`](https://requests.readthedocs.io).
- **Typed:** type hints throughout, `TypedDict`s for results, and a `py.typed`
  marker.

> Your API key can send email as your brand. Use the SDK server-side only, and
> never ship the key to a browser or a mobile app.

## Requirements

Python 3.9 or newer.

## Install

```bash
pip install skrybe-sdk
```

The package installs as `skrybe-sdk` and imports as `skrybe`.

## Quick start

```python
import os
from skrybe import Skrybe

skrybe = Skrybe(os.environ["SKRYBE_API_KEY"])

lists = skrybe.lists.list()

skrybe.subscribers.subscribe(
    list_id=lists[0]["id"],
    email="ada@example.com",
    name="Ada",
    fields={"Birthday": "1990-12-10"},
)

skrybe.emails.send_transactional(
    to_email="ada@example.com",
    subject="Your code",
    plain_body="Your code is 384092.",
)
```

Use a brand's API key, from Settings in the Skrybe dashboard.

### Options

```python
import requests

skrybe = Skrybe(
    api_key,
    base_url="https://dashboard.skry.be",  # the default
    timeout=30,         # seconds per attempt
    max_retries=2,      # reads only; see below
    session=requests.Session(),  # optional: your own, e.g. with proxies or a CA bundle
)
```

| Option | Default | |
|---|---|---|
| `api_key` | required | A brand's API key, from Settings in the Skrybe dashboard. |
| `base_url` | `https://dashboard.skry.be` | |
| `timeout` | `30` | Seconds per attempt. A timeout raises `ConnectionError` with `code == "timeout"` and is not retried. |
| `max_retries` | `2` | Extra attempts for **reads** after a dropped connection or a 429/502/503/504, honouring `Retry-After`. Writes are never retried: the API has no idempotency keys, so a retried send could go out twice. |
| `session` | a new `requests.Session` | Your own session, e.g. with `proxies` set or `verify` pointing at a corporate CA bundle. requests also honours `HTTPS_PROXY` and `REQUESTS_CA_BUNDLE`. |

`Skrybe` is a context manager (`with Skrybe(key) as skrybe: ...`), and
`skrybe.close()` closes the session it made. A session you pass in is left for
you to close.

Requests are logged on the `skrybe` logger at DEBUG level (method, path, status
and timing) and failures at WARNING. Request bodies are never logged, since they
carry the API key.

## Usage

Methods take snake_case keyword arguments. Results are plain dicts and lists
shaped as the API's JSON, so their keys are the API's snake_case names; the
shapes are described by the `TypedDict`s in `skrybe.types`.

List ids are encrypted strings, not the number in the dashboard URL: pass them
back exactly as the API returns them.

### Email

```python
# Transactional: one email, delivered immediately. OTPs, resets, receipts.
# from_name, from_email and reply_to fall back to the brand's.
result = skrybe.emails.send_transactional(
    to_email="ada@example.com",
    subject="Reset your password",
    html_body="<p>...</p>",
    plain_body="...",
)
# {"message": "...", "message_id": "..."}

# Bulk: up to 250 addresses, or whole lists. Creates a campaign behind the scenes.
result = skrybe.emails.send(
    from_name="Ada",
    from_email="ada@yourdomain.com",
    reply_to="ada@yourdomain.com",
    subject="Hello [recipient.first]",
    html_text="<p>Hi [recipient.first]!</p>",
    to=["user@example.com"],
    recipient_variables={"user@example.com": {"first": "John"}},
)
# {"message": "...", "campaign_id": "..."}
```

More than 250 `to` addresses raise `InvalidRequestError` (`too_many_recipients`)
before anything is sent; put them on a list and pass `list_ids` instead.

### Campaigns

```python
created = skrybe.campaigns.create(
    from_name="Ada",
    from_email="ada@yourdomain.com",
    reply_to="ada@yourdomain.com",
    title="October newsletter",
    subject="What we shipped",
    html_text="<p>...</p>",
)
campaign_id = int(created["campaign_id"])

skrybe.campaigns.test_send(campaign_id, ["me@yourdomain.com"])  # at most 5 addresses

# Count the recipients without sending, then send.
dry = skrybe.campaigns.send(campaign_id, list_ids=[list_id], dry_run=True)
print(dry["recipients"])
skrybe.campaigns.send(campaign_id, list_ids=[list_id])

# Or schedule it. Anything PHP's strtotime() reads.
skrybe.campaigns.schedule(campaign_id, list_ids=[list_id], at="2027-06-15 18:05", timezone="Africa/Lagos")
skrybe.campaigns.unschedule(campaign_id)

stats = skrybe.campaigns.stats(campaign_id)
clickers = skrybe.campaigns.activity_all(campaign_id, "clicks")
```

`create()` can also send (`send=True`) or schedule (`schedule_date_time=...`)
in the same call. It returns `{"outcome": "created" | "sending" | "scheduled",
"campaign_id": ...}`, and the id is only known for a plain create.

Also: `list(page=, limit=, status=)`, `list_all(status=)`,
`get(id, include_content=True)`, `update(id, subject=..., ...)`,
`duplicate(id, title=)`, `delete(id)` and `activity(id, type=, page=, limit=)`.
`send()` and `schedule()` take `list_ids`, `segment_ids`, `exclude_list_ids`
and `exclude_segment_ids`.

### Lists and custom fields

```python
lst = skrybe.lists.create("Customers", opt_in="single")
skrybe.lists.add_custom_field(lst["id"], "Birthday", type="date")
skrybe.lists.rename_custom_field(lst["id"], "Birthday", "Date of birth")

detail = skrybe.lists.get(lst["id"])  # opt-in, subscriber counts and custom fields
active = skrybe.lists.active_subscriber_count(lst["id"])
```

Also `list(include_hidden=True)`, `update(id, name=, opt_in=)`, `delete(id)` and
`delete_custom_field(id, name)`.

### Subscribers

```python
outcome = skrybe.subscribers.subscribe(list_id=list_id, email="ada@example.com", name="Ada")
# "subscribed", or "already_subscribed" (which updates the name and fields)

status = skrybe.subscribers.status(list_id, "ada@example.com")  # e.g. "Subscribed"
page = skrybe.subscribers.list(list_id, status="active", page=1, limit=100)
everyone = skrybe.subscribers.list_all(list_id, status="active")

skrybe.subscribers.unsubscribe(list_id, "ada@example.com")  # marks them unsubscribed
skrybe.subscribers.delete(list_id, "ada@example.com")       # removes the row outright
```

`subscribe()` also takes `country`, `ip_address`, `referrer`, `gdpr=True` and
`silent=True` (single opt-in on a double opt-in list). Custom `fields` are keyed
by the name the list shows; spaces are taken out of the names before sending, as
the server expects.

### Templates

```python
t = skrybe.templates.create(name="Welcome", html_text="<p>Welcome!</p>")
skrybe.templates.update(t["id"], from_name="Ada")
```

Also `list()`, `get(id, include_content=True)` for the HTML, and `delete(id)`.

### Autoresponders

```python
drip = skrybe.autoresponders.create(name="Onboarding", type="drip", list_id=list_id)
skrybe.autoresponders.create_email(
    drip["id"],
    subject="Day 3: getting started",
    html_text="<p>...</p>",
    when="+3 days",
    enabled=True,  # emails are created switched off unless you say otherwise
)

# annually and on_date send on a Date custom field of the list
skrybe.autoresponders.create(name="Birthdays", type="annually", list_id=list_id, custom_field="Birthday")
```

Also `list(list_id=)`, `get(id)` (with its emails under `email_list`) and
`email_stats(email_id)`.

### Brands and stats

```python
[brand] = skrybe.brands.list()  # the key's own brand
sent = skrybe.stats.total_emails_sent()  # installation-wide, public
```

## Errors

Every failure is a `SkrybeError` with a machine-readable `code`, a `type`, and
often a `hint`. Catch the subclass, or branch on `type` or `code`:

| Class | `type` | When |
|---|---|---|
| `AuthenticationError` | `authentication` | The API key is missing or wrong. |
| `InvalidRequestError` | `invalid_request` | The request is wrong; retrying it unchanged fails again. Includes `missing_params`, raised before anything is sent when a required argument is `None` or `""`. |
| `RateLimitError` | `rate_limit` | A quota or rate limit was hit (`quota_exceeded`, `rate_limited`). |
| `ConnectionError` | `connection` | The API could not be reached (`network_error`), or timed out (`timeout`). |
| `ApiError` | `api` | Anything else, e.g. `list_not_found`, `campaign_not_draft`, `unexpected_response`. |

```python
from skrybe import RateLimitError, SkrybeError

try:
    skrybe.campaigns.send(campaign_id, list_ids=[list_id])
except RateLimitError:
    ...  # quota_exceeded, rate_limited
except SkrybeError as err:
    if err.code == "campaign_not_draft":
        ...  # already sent
    else:
        raise
```

`err.raw` holds the response body and `err.status` the HTTP status, for
debugging. `skrybe.ConnectionError` is the SDK's own class, not Python's builtin
`ConnectionError`; import it under another name if you need both.

## Security

- **TLS is always verified** unless you pass a session that turns it off. Use
  the `session` option to supply a custom CA bundle or proxy instead.
- **Redirects are not followed**, so the API key in a request body is never
  replayed to another host. A redirect surfaces as an `ApiError` with its
  `status`.
- **Keep your CA store current.** requests trusts the `certifi` bundle, so CA
  distrust events (such as eMudhra's in October 2026) only reach you when you
  update `certifi`.

## Upgrading from 0.x

2.0 is a rewrite, and the version jumps from 0.1.0 to match the TypeScript and
PHP SDKs. **The import package is now `skrybe`** (it was `skrybe_sdk`); the PyPI
name stays `skrybe-sdk`. Methods moved onto resources, take snake_case keyword
arguments instead of a dict of camelCase options, and return parsed values
instead of raw response bodies:

| 0.x | 2.x |
|---|---|
| `from skrybe_sdk import SkrybeSDK` | `from skrybe import Skrybe` |
| `SkrybeSDK(api_key, base_url)` | `Skrybe(api_key, base_url=...)` |
| `send_email({...})` | `emails.send(from_name=..., ...)`, returns `{"message", "campaign_id"}` |
| `send_transactional({...})` | `emails.send_transactional(to_email=..., ...)`, returns `{"message", "message_id"}` |
| `create_campaign({...})` | `campaigns.create(...)`. `sendCampaign` is `send=True`. Returns `{"outcome", "campaign_id"}`. |
| `get_lists(include_hidden)` | `lists.list(include_hidden=...)`, returns `[{"id", "name"}]` |
| `get_campaigns({...})` | `campaigns.list(page=, limit=, status=)`, or `list_all()` |
| `get_subscribers(list_id, {...})` | `subscribers.list(list_id, ...)`, or `list_all(list_id)` |
| `add_subscriber(list_id, data)` | `subscribers.subscribe(list_id=..., email=..., ...)` |
| `SkrybeException` | `SkrybeError` and its subclasses |
| `ValidationException` | `InvalidRequestError` (`missing_params`, `body_missing`, ...) |

Failures now raise instead of being returned as a string, including the ones
the API reports with HTTP 200 such as "Invalid API key".

0.x bugs fixed along the way:

- `add_subscriber()` called `api/subscribers/add.php`, which does not exist.
- `create_campaign()` JSON-encoded list and segment ids; the API wants them
  comma-joined.
- `get_lists()` returned the raw `list1`/`list2` payload, and a list name
  containing a quote made it unparseable.
- Requests had no timeout, so a stalled connection hung forever.
- `send_transactional()` was not in the 0.1.0 release on PyPI.
- `python -m skrybe_sdk` imported Django, which was never a dependency.

## Development

```bash
python -m venv .venv && . .venv/bin/activate
pip install -e '.[dev]'
pytest
```

The tests run against a local HTTP server rather than mocks, since the API's
quirks are wire-level. Release notes go under `## [Unreleased]` in
`CHANGELOG.md`; the version lives in `src/skrybe/_version.py`, and a test fails
if it differs from the latest released heading in the changelog.

## License

MIT
