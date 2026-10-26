# Changelog

All notable changes to the Skrybe Python SDK (`skrybe-sdk` on PyPI) will be
documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Methods that call new API endpoints need a Skrybe install that has them
deployed; the API side lives in skry-be/skrybe-dashboard.

## [Unreleased]

## [2.0.0] - 2026-10-26

A rewrite covering the whole public API, in step with `@skrybe/sdk` 2.0.0 and
`skrybe/sdk-php` 2.0.0. The version jumps from 0.1.0 to 2.0.0 to match them.
See "Upgrading from 0.x" in the README.

### Added
- A `Skrybe` client with resources: `emails`, `campaigns`, `lists`,
  `subscribers`, `templates`, `autoresponders`, `brands`, `stats`.
- Emails: `send` and `send_transactional`.
- Campaigns: `create`, `list`/`list_all`, `get`, `stats`, `send` (with
  `dry_run`), `test_send`, `schedule`/`unschedule`, `update`, `duplicate`,
  `delete`, `activity`/`activity_all`.
- Lists: `list`, `get`, `create`, `update`, `delete`,
  `active_subscriber_count`, and custom fields (`add_custom_field`,
  `rename_custom_field`, `delete_custom_field`).
- Subscribers: `subscribe` (with custom fields), `unsubscribe`, `delete`,
  `status`, `list`/`list_all`.
- Templates: `list`, `get`, `create`, `update`, `delete`.
- Autoresponders: `list`, `get`, `email_stats`, `create`, `create_email`.
- `brands.list()` and `stats.total_emails_sent()`.
- Typed exceptions under `SkrybeError`: `AuthenticationError`,
  `InvalidRequestError`, `RateLimitError`, `ConnectionError` and `ApiError`,
  each with a stable `code`, a `type`, and where known a `hint`, plus the
  response's `status` and `raw` body. Prose failures the API returns with
  HTTP 200 are recognised and raised.
- `timeout`, `max_retries` (reads only, honouring `Retry-After`) and `session`
  (proxies, CA bundles) options.
- Type hints throughout, `TypedDict`s for results in `skrybe.types`, and a
  `py.typed` marker.
- Request logging on the `skrybe` logger: method, path, status and timing,
  never bodies.

### Changed
- The import package is now `skrybe` instead of `skrybe_sdk`, and
  `SkrybeSDK(api_key)` is `Skrybe(api_key)`.
- Methods take snake_case keyword arguments instead of a dict of camelCase
  options, return parsed results, and raise on failure instead of returning
  whatever the response body was.
- `campaigns.create()` takes `send=True` instead of `sendCampaign`, and id
  lists as Python lists.
- Requires Python 3.9 or newer (was 3.7).

### Removed
- `ValidationException` and the client-side `@` checks on addresses; missing
  parameters raise `InvalidRequestError` with the code `missing_params`, and
  the API validates addresses.
- The client-side 100ms request spacing.
- `python -m skrybe_sdk`, which imported Django without depending on it.

### Fixed
- `add_subscriber()` called `api/subscribers/add.php`, which does not exist;
  `subscribers.subscribe()` replaces it.
- `create_campaign()` sent list and segment ids JSON-encoded; they are
  comma-joined, as the API expects.
- `get_lists()` returned the raw `list1`/`list2` payload, and a list name
  containing a quote made it unparseable.
- Failures the API reports with HTTP 200 (e.g. "Invalid API key") were returned
  as if they had succeeded.
- Requests had no timeout and could hang forever.
- `send_transactional()` was missing from the 0.1.0 release on PyPI.
- The package metadata named a nonexistent `skrybe-sdk-django` project and a
  placeholder author; build artifacts are no longer committed.

## [0.1.0] - 2025-05-29

### Added
- Initial release: `SkrybeSDK` with `send_email`, `create_campaign`,
  `get_lists`, `get_campaigns`, `get_subscribers` and `add_subscriber`.
