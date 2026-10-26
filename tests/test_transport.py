import builtins
import logging
import socket

import pytest
import requests

import skrybe
from skrybe import (
    VERSION,
    ApiError,
    AuthenticationError,
    ConnectionError,
    InvalidRequestError,
    RateLimitError,
    Skrybe,
    SkrybeError,
)
from skrybe.errors import classify_prose, code_for_status, type_for_status

from .conftest import KEY, Reply


def test_requires_an_api_key():
    with pytest.raises(InvalidRequestError) as info:
        Skrybe("")
    assert info.value.code == "api_key_missing"


def test_defaults_to_the_production_api():
    seen = []

    class Recording(requests.Session):
        def request(self, method, url, **kwargs):
            seen.append(url)
            response = requests.Response()
            response.status_code = 200
            response._content = b"4"
            return response

    client = Skrybe(KEY, session=Recording())
    assert client.lists.active_subscriber_count("abc") == 4
    assert seen == ["https://dashboard.skry.be/api/subscribers/active-subscriber-count.php"]


def test_posts_a_form_body_with_the_api_key_and_a_user_agent(stub):
    s = stub(["4211"])
    client = Skrybe(KEY, base_url=s.url + "///")

    assert client.lists.active_subscriber_count("AbC892763xy") == 4211
    assert len(s.received) == 1
    r = s.received[0]
    assert r.method == "POST"
    assert r.path == "/api/subscribers/active-subscriber-count.php"
    assert r.content_type == "application/x-www-form-urlencoded"
    assert r.fields == {"list_id": "AbC892763xy", "api_key": KEY}
    assert r.raw_body == "list_id=AbC892763xy&api_key=test-api-key"
    assert r.headers["User-Agent"] == f"skrybe-sdk-py/{VERSION}"


def test_turns_a_prose_failure_carried_by_http_200_into_a_typed_error(stub):
    s = stub(["Invalid API key"])
    client = Skrybe("wrong", base_url=s.url)

    with pytest.raises(AuthenticationError) as info:
        client.lists.list()
    err = info.value
    assert isinstance(err, SkrybeError)
    assert err.type == "authentication"
    assert err.code == "invalid_api_key"
    assert err.status == 200
    assert err.raw == "Invalid API key"
    assert str(err) == "Invalid API key"
    assert err.hint


@pytest.mark.parametrize(
    "body, kind, code",
    [
        ("List does not exist", ApiError, "list_not_found"),
        ("List ID not passed", InvalidRequestError, "list_id_invalid"),
        ("API key not passed", AuthenticationError, "api_key_missing"),
        ("Quota exceeded. Please upgrade your plan.", RateLimitError, "quota_exceeded"),
        ("Error: this campaign would exceed your monthly limit", RateLimitError, "quota_exceeded"),
        ("Test send rate limit reached, try later", RateLimitError, "rate_limited"),
        ("Unable to insert campaign", ApiError, "operation_failed"),
        ("List already has a drip autoresponder", ApiError, "drip_exists"),
        ("Account under review: high bounces", ApiError, "account_under_review"),
        ('Domain "example.com" is not verified', ApiError, "domain_not_verified"),
        ("  campaign does not exist \n", ApiError, "campaign_not_found"),
    ],
)
def test_classifies_prose_by_kind(stub, body, kind, code):
    s = stub([body])
    client = Skrybe(KEY, base_url=s.url)
    with pytest.raises(kind) as info:
        client.lists.get("x")
    assert type(info.value) is kind
    assert info.value.code == code
    assert info.value.type == kind.type


def test_classify_prose_leaves_data_alone():
    assert classify_prose('{"id": 1}') is None
    assert classify_prose("Subscribed") is None
    assert classify_prose("") is None


def test_status_mapping():
    assert [type_for_status(s) for s in (400, 401, 402, 403, 404, 405, 422, 429, 500)] == [
        "invalid_request",
        "authentication",
        "rate_limit",
        "authentication",
        "api",
        "invalid_request",
        "invalid_request",
        "rate_limit",
        "api",
    ]
    assert [code_for_status(s) for s in (400, 401, 402, 403, 404, 405, 418, 429, 503)] == [
        "invalid_request",
        "unauthenticated",
        "quota_exceeded",
        "forbidden",
        "not_found",
        "method_not_allowed",
        "api_error",
        "rate_limited",
        "server_error",
    ]


def test_reads_the_error_out_of_a_json_endpoints_envelope_and_status(stub):
    s = stub([Reply(status=400, body='{"ok":false,"error":"Invalid from_email"}')])
    client = Skrybe(KEY, base_url=s.url)

    with pytest.raises(InvalidRequestError) as info:
        client.emails.send(from_name="a", from_email="b", reply_to="c", subject="d", html_text="e", to=["x@y.z"])
    assert str(info.value) == "Invalid from_email"
    assert info.value.status == 400
    assert info.value.code == "invalid_request"


def test_reads_the_transactional_error_envelope(stub):
    s = stub([Reply(status=401, body='{"status":"error","message":"Invalid API key"}')])
    client = Skrybe(KEY, base_url=s.url)
    with pytest.raises(AuthenticationError) as info:
        client.emails.send_transactional(to_email="a@b.c", subject="s", plain_body="p")
    assert str(info.value) == "Invalid API key"
    assert info.value.code == "unauthenticated"


def test_an_empty_error_body_gets_a_message(stub):
    s = stub([Reply(status=500, body="")])
    client = Skrybe(KEY, base_url=s.url, max_retries=0)
    with pytest.raises(ApiError) as info:
        client.templates.delete(1)
    assert str(info.value) == "HTTP 500 from the Skrybe API."
    assert info.value.code == "server_error"


def test_retries_a_read_on_503_honouring_retry_after(stub):
    s = stub([Reply(status=503, headers={"Retry-After": "0"}), "7"])
    client = Skrybe(KEY, base_url=s.url)
    assert client.lists.active_subscriber_count("x") == 7
    assert len(s.received) == 2


@pytest.mark.parametrize("status", [429, 502, 504])
def test_retries_a_read_on_other_retryable_statuses(stub, status):
    s = stub([Reply(status=status, headers={"Retry-After": "0"}), '{"templates":[]}'])
    client = Skrybe(KEY, base_url=s.url)
    assert client.templates.list() == []
    assert len(s.received) == 2


def test_gives_up_after_max_retries(stub):
    s = stub([Reply(status=503, headers={"Retry-After": "0"})])
    client = Skrybe(KEY, base_url=s.url, max_retries=2)
    with pytest.raises(ApiError) as info:
        client.lists.active_subscriber_count("x")
    assert info.value.status == 503
    assert len(s.received) == 3


def test_does_not_retry_a_500(stub):
    s = stub([Reply(status=500, headers={"Retry-After": "0"})])
    client = Skrybe(KEY, base_url=s.url)
    with pytest.raises(ApiError):
        client.lists.active_subscriber_count("x")
    assert len(s.received) == 1


def test_never_retries_a_write(stub):
    s = stub([Reply(status=503, headers={"Retry-After": "0"})])
    client = Skrybe(KEY, base_url=s.url)
    with pytest.raises(ApiError):
        client.campaigns.send(1, list_ids=["a"])
    assert len(s.received) == 1


def test_respects_max_retries_zero(stub):
    s = stub([Reply(status=503, headers={"Retry-After": "0"})])
    client = Skrybe(KEY, base_url=s.url, max_retries=0)
    with pytest.raises(SkrybeError):
        client.lists.active_subscriber_count("x")
    assert len(s.received) == 1


def test_times_out_as_a_connection_error_without_retrying(stub):
    s = stub([Reply(body="1", delay=0.5)])
    client = Skrybe(KEY, base_url=s.url, timeout=0.05)
    with pytest.raises(ConnectionError) as info:
        client.lists.active_subscriber_count("x")  # a read, so retryable, but not on timeout
    assert info.value.code == "timeout"
    assert info.value.type == "connection"
    assert len(s.received) == 1


def _closed_port():
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


def test_reports_an_unreachable_host_as_a_connection_error():
    client = Skrybe(KEY, base_url=f"http://127.0.0.1:{_closed_port()}", max_retries=0)
    with pytest.raises(ConnectionError) as info:
        client.brands.list()
    assert info.value.code == "network_error"
    assert isinstance(info.value.__cause__, requests.ConnectionError)
    # Not the builtin: it is a SkrybeError.
    assert isinstance(info.value, SkrybeError)
    assert skrybe.ConnectionError is not builtins.ConnectionError


def test_retries_a_dropped_connection_on_a_read(stub):
    calls = []

    class Flaky(requests.Session):
        def request(self, method, url, **kwargs):
            calls.append(url)
            if len(calls) == 1:
                raise requests.ConnectionError("Connection reset")
            return super().request(method, url, **kwargs)

    s = stub(["3"])
    client = Skrybe(KEY, base_url=s.url, max_retries=1, session=Flaky())
    assert client.lists.active_subscriber_count("x") == 3
    assert len(calls) == 2


def test_does_not_follow_redirects(stub):
    s = stub([Reply(status=302, headers={"Location": "http://example.invalid/"})])
    client = Skrybe(KEY, base_url=s.url)
    with pytest.raises(ApiError) as info:
        client.templates.delete(1)
    assert info.value.status == 302


def test_never_logs_the_api_key(stub, caplog):
    s = stub([Reply(status=503, headers={"Retry-After": "0"}), "7"])
    client = Skrybe(KEY, base_url=s.url)
    with caplog.at_level(logging.DEBUG, logger="skrybe"):
        client.lists.active_subscriber_count("x")
    assert caplog.records, "expected request logs"
    assert all(KEY not in r.getMessage() for r in caplog.records)


def test_repr_does_not_show_the_key():
    assert KEY not in repr(Skrybe(KEY))
