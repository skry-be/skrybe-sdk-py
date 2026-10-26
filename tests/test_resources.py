import json

import pytest

from skrybe import ApiError, InvalidRequestError, Skrybe

from .conftest import KEY, php_numbered_payload

DRAFT = dict(from_name="a", from_email="b@c.d", reply_to="b@c.d", title="t", subject="s", html_text="h")
EMAIL = dict(from_name="a", from_email="b", reply_to="c", subject="d", html_text="e")


# ---------------------------------------------------------------- emails


def test_send_posts_recipients_as_json_strings_inside_a_form_body(setup):
    s, client = setup(['{"ok":true,"message":"Queued","data":{"campaign_id":"c1"}}'])

    result = client.emails.send(
        from_name="Ada",
        from_email="ada@example.com",
        reply_to="ada@example.com",
        subject="Hi",
        html_text="<p>Hi [recipient.first]</p>",
        to=["a@example.com"],
        recipient_variables={"a@example.com": {"first": "A"}},
        track_opens=1,
        track_clicks=0,
    )

    assert result == {"message": "Queued", "campaign_id": "c1"}
    assert s.received[0].path == "/api/emails/send.php"
    assert s.sent() == {
        "from_name": "Ada",
        "from_email": "ada@example.com",
        "reply_to": "ada@example.com",
        "subject": "Hi",
        "html_text": "<p>Hi [recipient.first]</p>",
        "to": '["a@example.com"]',
        "recipient-variables": '{"a@example.com":{"first":"A"}}',
        "track_opens": "1",
        # 0 means off, and is sent rather than dropped.
        "track_clicks": "0",
    }


def test_send_to_lists_comma_joins_them(setup):
    s, client = setup(['{"ok":true,"message":"Queued"}'])
    assert client.emails.send(**EMAIL, list_ids=["L1", "L2"]) == {"message": "Queued", "campaign_id": None}
    assert s.sent()["list_ids"] == "L1,L2"
    assert "to" not in s.sent()


def test_send_refuses_before_any_request_with_nobody_or_too_many_to_send_to(setup):
    s, client = setup(["{}"])

    with pytest.raises(InvalidRequestError) as info:
        client.emails.send(**EMAIL)
    assert info.value.code == "recipients_missing"

    many = [f"u{i}@example.com" for i in range(251)]
    with pytest.raises(InvalidRequestError) as info:
        client.emails.send(**EMAIL, to=many)
    assert info.value.code == "too_many_recipients"
    assert len(s.received) == 0


def test_send_accepts_exactly_250(setup):
    s, client = setup(['{"ok":true}'])
    client.emails.send(**EMAIL, to=[f"u{i}@example.com" for i in range(250)])
    assert len(json.loads(s.sent()["to"])) == 250


def test_missing_required_params_are_caught_before_sending(setup):
    s, client = setup(["{}"])

    with pytest.raises(InvalidRequestError) as info:
        client.campaigns.create(**{**DRAFT, "from_name": "", "subject": None})
    assert info.value.code == "missing_params"
    assert "from_name" in str(info.value) and "subject" in str(info.value)

    for call in (
        lambda: client.emails.send(**{**EMAIL, "reply_to": ""}, to=["x@y.z"]),
        lambda: client.emails.send_transactional(to_email="", subject="s", plain_body="p"),
        lambda: client.subscribers.subscribe(list_id="", email="a@b.c"),
        lambda: client.templates.create(name="n", html_text=""),
        lambda: client.campaigns.schedule(1, at="", list_ids=["A"]),
        lambda: client.autoresponders.create(name="n", type="drip", list_id=""),
        lambda: client.autoresponders.create_email(1, subject="", html_text="h"),
    ):
        with pytest.raises(InvalidRequestError) as info:
            call()
        assert info.value.code == "missing_params"
    assert len(s.received) == 0


def test_send_transactional_posts_raw_json(setup):
    s, client = setup(['{"status":"success","message":"Sent","message_id":"m1"}'])

    result = client.emails.send_transactional(to_email="a@example.com", subject="OTP", plain_body="1234")

    assert result == {"message": "Sent", "message_id": "m1"}
    assert s.received[0].path == "/api/emails/send-transactional.php"
    assert s.received[0].content_type == "application/json"
    assert json.loads(s.received[0].raw_body) == {
        "to_email": "a@example.com",
        "subject": "OTP",
        "plain_body": "1234",
        "api_key": KEY,
    }


def test_send_transactional_needs_a_body(setup):
    s, client = setup(["{}"])
    with pytest.raises(InvalidRequestError) as info:
        client.emails.send_transactional(to_email="a@b.c", subject="s")
    assert info.value.code == "body_missing"
    assert len(s.received) == 0


# ------------------------------------------------------------- campaigns


def test_create_returns_the_new_id_from_the_json_answer(setup):
    s, client = setup(['{"status":"Campaign created","campaign_id":"42"}'])

    assert client.campaigns.create(**DRAFT, list_ids=["L1", "L2"], exclude_segment_ids=[3, 4]) == {
        "outcome": "created",
        "campaign_id": "42",
    }
    fields = s.sent()
    assert s.received[0].path == "/api/campaigns/create.php"
    assert fields["json"] == "1"
    assert fields["list_ids"] == "L1,L2"
    # Sic: create.php reads exclude_segments_ids.
    assert fields["exclude_segments_ids"] == "3,4"
    assert "exclude_segment_ids" not in fields
    assert "send_campaign" not in fields


def test_create_reports_sending_and_scheduled_outcomes(setup):
    s, client = setup(["Campaign created and now sending"])
    assert client.campaigns.create(**DRAFT, list_ids=["L"], send=True) == {"outcome": "sending", "campaign_id": None}
    assert s.sent()["send_campaign"] == "1"

    _, client = setup(["Campaign scheduled"])
    assert client.campaigns.create(**DRAFT, schedule_date_time="June 1, 2027 6:05pm") == {
        "outcome": "scheduled",
        "campaign_id": None,
    }

    _, client = setup(["Campaign created"])
    assert client.campaigns.create(**DRAFT) == {"outcome": "created", "campaign_id": None}


def test_create_does_not_mistake_an_unknown_body_for_success(setup):
    _, client = setup(["<html>Bad gateway</html>"])
    with pytest.raises(ApiError) as info:
        client.campaigns.create(**DRAFT)
    assert info.value.code == "unexpected_response"
    assert info.value.raw == "<html>Bad gateway</html>"


def test_list_reads_numbered_records_and_no_campaigns_found_as_empty(setup):
    row = {"id": 3, "title": "T", "status": "sent"}
    s, client = setup([json.dumps({"campaign1": row})])
    assert client.campaigns.list(status="sent", limit=10) == [row]
    assert s.sent() == {"status": "sent", "limit": "10"}

    _, client = setup(["No campaigns found"])
    assert client.campaigns.list() == []


def test_list_all_walks_pages_until_a_short_one(setup):
    def page(n):
        return json.dumps({f"campaign{i + 1}": {"id": i} for i in range(n)})

    s, client = setup([page(100), page(3)])
    assert len(client.campaigns.list_all(status="sent")) == 103
    assert [r.fields["page"] for r in s.received] == ["1", "2"]
    assert {r.fields["limit"] for r in s.received} == {"100"}
    assert {r.fields["status"] for r in s.received} == {"sent"}


def test_send_and_schedule_pass_recipients_and_dry_run_only_when_asked(setup):
    s, client = setup(['{"status":"sending","campaign_id":5,"recipients":10}'])
    assert client.campaigns.send(5, list_ids=["A"], segment_ids=[7], exclude_list_ids=["B"], exclude_segment_ids=[8]) == {
        "status": "sending",
        "campaign_id": 5,
        "recipients": 10,
    }
    assert s.received[0].path == "/api/campaigns/send.php"
    assert s.sent() == {
        "campaign_id": "5",
        "list_ids": "A",
        "segment_ids": "7",
        "exclude_list_ids": "B",
        # send.php and schedule.php spell it without the extra s.
        "exclude_segment_ids": "8",
    }

    s, client = setup(['{"status":"dry_run","campaign_id":5,"recipients":10,"scheduled_at":1,"timezone":"Africa/Lagos"}'])
    client.campaigns.schedule(5, list_ids=["A"], at="2027-06-15 18:05", timezone="Africa/Lagos", dry_run=True)
    assert s.received[0].path == "/api/campaigns/schedule.php"
    assert s.sent() == {
        "campaign_id": "5",
        "list_ids": "A",
        "schedule_date_time": "2027-06-15 18:05",
        "schedule_timezone": "Africa/Lagos",
        "dry_run": "1",
    }


@pytest.mark.parametrize(
    "path, call",
    [
        ("/api/campaigns/get-campaign.php", lambda c: c.campaigns.get(1, include_content=True)),
        ("/api/campaigns/stats.php", lambda c: c.campaigns.stats(1)),
        ("/api/campaigns/test-send.php", lambda c: c.campaigns.test_send(1, ["a@b.c"])),
        ("/api/campaigns/unschedule.php", lambda c: c.campaigns.unschedule(1)),
        ("/api/campaigns/update-campaign.php", lambda c: c.campaigns.update(1, subject="x")),
        ("/api/campaigns/duplicate-campaign.php", lambda c: c.campaigns.duplicate(1)),
        ("/api/campaigns/delete-campaign.php", lambda c: c.campaigns.delete(1)),
        ("/api/campaigns/get-activity.php", lambda c: c.campaigns.activity(1, type="clicks")),
    ],
)
def test_each_campaign_endpoint_posts_to_its_own_path(setup, path, call):
    s, client = setup(['{"campaign_id":1}'])
    assert call(client) == {"campaign_id": 1}
    assert s.received[0].path == path
    assert s.received[0].fields["campaign_id"] == "1"


def test_campaign_field_names(setup):
    s, client = setup(['{"campaign_id":1}'])
    client.campaigns.get(1, include_content=True)
    assert s.sent() == {"campaign_id": "1", "include_content": "yes"}

    s, client = setup(['{"campaign_id":1}'])
    client.campaigns.test_send(1, ["a@b.c", "d@e.f"])
    assert s.sent() == {"campaign_id": "1", "emails": "a@b.c,d@e.f"}

    s, client = setup(['{"campaign_id":1}'])
    client.campaigns.update(1, from_name="Ada", track_opens=2, preheader="P")
    assert s.sent() == {"campaign_id": "1", "from_name": "Ada", "track_opens": "2", "preheader": "P"}

    s, client = setup(['{"campaign_id":1}'])
    client.campaigns.duplicate(1, title="Copy")
    assert s.sent() == {"campaign_id": "1", "title": "Copy"}

    s, client = setup(['{"campaign_id":1}'])
    client.campaigns.activity(1, type="opens", page=2, limit=50)
    assert s.sent() == {"campaign_id": "1", "type": "opens", "page": "2", "limit": "50"}


def test_activity_all_stops_at_the_total(setup):
    def page(n, total):
        return json.dumps({"activity": [{"email": "a@b.c"}] * n, "total": total})

    s, client = setup([page(1000, 1500), page(500, 1500)])
    assert len(client.campaigns.activity_all(1, "opens")) == 1500
    assert len(s.received) == 2
    assert s.received[1].fields["page"] == "2"
    assert s.received[1].fields["limit"] == "1000"


def test_campaign_prose_errors(setup):
    _, client = setup(["Campaign does not exist"])
    with pytest.raises(ApiError) as info:
        client.campaigns.get(999999)
    assert info.value.code == "campaign_not_found"

    _, client = setup(["Campaign has already been sent"])
    with pytest.raises(ApiError) as info:
        client.campaigns.send(1, list_ids=["A"])
    assert info.value.code == "campaign_not_draft"


# ----------------------------------------------------------------- lists


def test_list_survives_an_unescaped_quote_in_a_name(setup):
    s, client = setup([php_numbered_payload("list", [{"id": "A1", "name": 'Q4 "Big" Push'}])])
    assert client.lists.list() == [{"id": "A1", "name": 'Q4 "Big" Push'}]
    assert s.sent() == {"include_hidden": "no"}

    s, client = setup(["No lists found"])
    assert client.lists.list(include_hidden=True) == []
    assert s.sent() == {"include_hidden": "yes"}


def test_active_subscriber_count_never_reports_a_failure_as_zero(setup):
    _, client = setup(["<b>Warning</b>"])
    with pytest.raises(ApiError) as info:
        client.lists.active_subscriber_count("A1")
    assert info.value.code == "malformed_response"

    _, client = setup([""])
    with pytest.raises(ApiError):
        client.lists.active_subscriber_count("A1")


def test_manages_custom_fields(setup):
    s, client = setup(['{"id":"A1"}'])
    client.lists.rename_custom_field("A1", "Birthday", "DOB")
    assert s.received[0].path == "/api/lists/rename-custom-field.php"
    assert s.sent() == {"list_id": "A1", "name": "Birthday", "new_name": "DOB"}

    s, client = setup(['{"id":"A1"}'])
    client.lists.add_custom_field("A1", "DOB", type="date")
    assert s.received[0].path == "/api/lists/add-custom-field.php"
    assert s.sent() == {"list_id": "A1", "name": "DOB", "type": "date"}

    s, client = setup(['{"id":"A1"}'])
    client.lists.delete_custom_field("A1", "DOB")
    assert s.received[0].path == "/api/lists/delete-custom-field.php"
    assert s.sent() == {"list_id": "A1", "name": "DOB"}


def test_create_update_get_and_delete_list(setup):
    s, client = setup(['{"id":"A1","name":"Customers"}'])
    assert client.lists.create("Customers", opt_in="double") == {"id": "A1", "name": "Customers"}
    assert s.received[0].path == "/api/lists/create.php"
    assert s.sent() == {"name": "Customers", "opt_in": "double"}

    s, client = setup(['{"id":"A1"}'])
    client.lists.update("A1", name="Renamed")
    assert s.received[0].path == "/api/lists/update-list.php"
    assert s.sent() == {"list_id": "A1", "name": "Renamed"}

    s, client = setup(['{"id":"A1"}'])
    client.lists.get("A1")
    assert s.received[0].path == "/api/lists/get-list.php"
    assert s.sent() == {"list_id": "A1"}

    s, client = setup(['{"id":"A1","deleted":true}'])
    assert client.lists.delete("A1") == {"id": "A1", "deleted": True}
    assert s.received[0].path == "/api/lists/delete.php"


# ----------------------------------------------------------- subscribers


def test_subscribe_posts_to_the_root_endpoint_in_plain_text_mode(setup):
    s, client = setup(["1"])

    outcome = client.subscribers.subscribe(
        list_id="A1",
        email="a@example.com",
        name="Ada",
        gdpr=True,
        ip_address="1.2.3.4",
        fields={"Favourite colour": "blue", "email": "forged@example.com"},
    )

    assert outcome == "subscribed"
    assert s.received[0].path == "/subscribe"
    assert s.sent() == {
        "Favouritecolour": "blue",
        "email": "a@example.com",
        "list": "A1",
        "boolean": "true",
        "name": "Ada",
        "ipaddress": "1.2.3.4",
        "gdpr": "true",
    }
    # Custom fields go first, so the documented names win a collision.
    assert s.received[0].raw_body.startswith("Favouritecolour=blue&email=a%40example.com&")


def test_subscribe_reports_an_existing_address_rather_than_raising(setup):
    _, client = setup(["Already subscribed."])
    assert client.subscribers.subscribe(list_id="A1", email="a@b.c") == "already_subscribed"

    _, client = setup(["true"])
    assert client.subscribers.subscribe(list_id="A1", email="a@b.c", silent=True) == "subscribed"


def test_unsubscribe_delete_and_status_use_their_own_field_names(setup):
    s, client = setup(["true"])
    assert client.subscribers.unsubscribe("A1", "a@b.c") is None
    assert s.received[0].path == "/unsubscribe"
    assert s.sent() == {"email": "a@b.c", "list": "A1", "boolean": "true"}

    s, client = setup(["true"])
    client.subscribers.delete(list_id="A1", email="a@b.c")
    assert s.received[0].path == "/api/subscribers/delete.php"
    assert s.sent() == {"list_id": "A1", "email": "a@b.c"}

    s, client = setup(["Soft bounced\n"])
    assert client.subscribers.status("A1", "a@b.c") == "Soft bounced"
    assert s.received[0].path == "/api/subscribers/subscription-status.php"
    assert s.sent() == {"email": "a@b.c", "list_id": "A1"}


def test_does_not_report_an_unrecognised_body_as_success(setup):
    _, client = setup(["Something new"])
    with pytest.raises(ApiError) as info:
        client.subscribers.unsubscribe("A1", "a@b.c")
    assert info.value.code == "unexpected_response"

    _, client = setup(["Something new"])
    with pytest.raises(ApiError):
        client.subscribers.subscribe(list_id="A1", email="a@b.c")

    _, client = setup(["  "])
    with pytest.raises(ApiError):
        client.subscribers.status("A1", "a@b.c")


def test_subscriber_prose_errors(setup):
    _, client = setup(["Email does not exist."])
    with pytest.raises(ApiError) as info:
        client.subscribers.unsubscribe("A1", "a@b.c")
    assert info.value.code == "subscriber_not_found"

    _, client = setup(["Invalid email address."])
    with pytest.raises(InvalidRequestError) as info:
        client.subscribers.subscribe(list_id="A1", email="nope")
    assert info.value.code == "invalid_email"


def test_list_all_subscribers_walks_pages_of_1000(setup):
    def page(n):
        return json.dumps({"subscribers": [{}] * n, "total": 1001})

    s, client = setup([page(1000), page(1)])
    assert len(client.subscribers.list_all("A1", status="active")) == 1001
    assert s.received[1].fields == {"list_id": "A1", "status": "active", "page": "2", "limit": "1000", "api_key": KEY}
    assert s.received[1].path == "/api/subscribers/get-subscribers.php"


# ------------------------------------------------------------- templates


def test_template_create_maps_onto_the_api_fields(setup):
    s, client = setup(['{"id":9,"name":"Welcome"}'])
    assert client.templates.create(name="Welcome", html_text="<p/>", editor="html") == {"id": 9, "name": "Welcome"}
    assert s.received[0].path == "/api/templates/create-template.php"
    assert s.sent() == {"name": "Welcome", "html_text": "<p/>", "editor": "html"}


def test_template_list_get_update_delete(setup):
    s, client = setup(['{"templates":[{"id":1}]}'])
    assert client.templates.list() == [{"id": 1}]
    assert s.received[0].path == "/api/templates/get-templates.php"

    s, client = setup(['{"id":1}'])
    client.templates.get(1, include_content=True)
    assert s.received[0].path == "/api/templates/get-template.php"
    assert s.sent() == {"template_id": "1", "include_content": "yes"}

    s, client = setup(['{"id":1}'])
    client.templates.update(1, from_name="Ada", reply_to="r@x.y")
    assert s.received[0].path == "/api/templates/update-template.php"
    assert s.sent() == {"template_id": "1", "from_name": "Ada", "reply_to": "r@x.y"}

    s, client = setup(['{"template_id":1,"deleted":true}'])
    assert client.templates.delete(1) == {"template_id": 1, "deleted": True}
    assert s.received[0].path == "/api/templates/delete-template.php"


# -------------------------------------------------------- autoresponders


def test_autoresponder_create_posts_the_type_and_list(setup):
    s, client = setup(['{"id":4,"name":"Birthdays","type":"annually"}'])
    client.autoresponders.create(name="Birthdays", type="annually", list_id="A1", custom_field="Birthday")
    assert s.received[0].path == "/api/autoresponders/create-autoresponder.php"
    assert s.sent() == {"name": "Birthdays", "type": "annually", "list_id": "A1", "custom_field": "Birthday"}


def test_create_email_sends_enabled_only_when_asked(setup):
    s, client = setup(['{"id":8,"autoresponder_id":4,"when":"+3 days"}'])
    client.autoresponders.create_email(4, subject="Day 3", html_text="<p/>", when="+3 days")
    assert s.received[0].path == "/api/autoresponders/create-autoresponder-email.php"
    assert s.sent() == {"autoresponder_id": "4", "subject": "Day 3", "html_text": "<p/>", "when": "+3 days"}

    s, client = setup(['{"id":8}'])
    client.autoresponders.create_email(4, subject="s", html_text="h", enabled=True)
    assert s.sent()["enabled"] == "1"


def test_surfaces_the_servers_when_validation_as_an_invalid_request(setup):
    _, client = setup(["when must be immediately, or a delay such as +3 days"])
    with pytest.raises(InvalidRequestError) as info:
        client.autoresponders.create_email(4, subject="s", html_text="h", when="soon")
    assert info.value.code == "invalid_when"


def test_autoresponder_list_get_and_stats(setup):
    s, client = setup(['{"autoresponders":[{"id":1}]}'])
    assert client.autoresponders.list(list_id="A1") == [{"id": 1}]
    assert s.received[0].path == "/api/autoresponders/get-autoresponders.php"
    assert s.sent() == {"list_id": "A1"}

    s, client = setup(['{"id":1,"email_list":[]}'])
    client.autoresponders.get(1)
    assert s.received[0].path == "/api/autoresponders/get-autoresponder-emails.php"
    assert s.sent() == {"autoresponder_id": "1"}

    s, client = setup(['{"id":8}'])
    client.autoresponders.email_stats(8)
    assert s.received[0].path == "/api/autoresponders/autoresponder-stats.php"
    assert s.sent() == {"email_id": "8"}


# ------------------------------------------------------ brands and stats


def test_brands_list_reads_the_numbered_payload(setup):
    s, client = setup([php_numbered_payload("brand", [{"id": "86", "name": "Cafe One"}])])
    assert client.brands.list() == [{"id": "86", "name": "Cafe One"}]
    assert s.received[0].path == "/api/brands/get-brands.php"
    assert s.sent() == {}

    _, client = setup(["No brands found"])
    assert client.brands.list() == []


def test_total_emails_sent_is_a_get_without_the_api_key(setup):
    s, client = setup(['{"total_emails_sent":123}'])
    assert client.stats.total_emails_sent() == 123
    assert s.received[0].method == "GET"
    assert s.received[0].path == "/api/stats/emails-sent.php"
    assert s.received[0].fields == {}
    assert s.received[0].raw_body == ""


def test_resources_are_attached():
    client = Skrybe(KEY)
    for name in ("emails", "campaigns", "lists", "subscribers", "templates", "autoresponders", "brands", "stats"):
        assert getattr(client, name) is not None
