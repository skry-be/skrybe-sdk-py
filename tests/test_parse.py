import json

import pytest

from skrybe import ApiError
from skrybe._parse import parse_json_object, parse_numbered_object, parse_numbered_records
from skrybe.errors import excerpt

from .conftest import php_numbered_payload


def test_reads_a_well_formed_payload():
    body = php_numbered_payload(
        "list",
        [{"id": "AbC892763xy", "name": "Newsletter"}, {"id": "ZzZ763892qq", "name": "Announcements"}],
    )
    assert parse_numbered_object(body, "list") == [
        {"id": "AbC892763xy", "name": "Newsletter"},
        {"id": "ZzZ763892qq", "name": "Announcements"},
    ]


def test_reads_the_brand_payload_whose_ids_are_bare_integers():
    body = php_numbered_payload("brand", [{"id": "86", "name": "Cafe One"}])
    assert parse_numbered_object(body, "brand") == [{"id": "86", "name": "Cafe One"}]
    # And once the endpoint json_encode()s a real integer.
    assert parse_numbered_object('{"brand1": {"id": 86, "name": "Cafe One"}}', "brand") == [
        {"id": "86", "name": "Cafe One"}
    ]


def test_returns_an_empty_list_for_an_empty_body():
    assert parse_numbered_object("", "list") == []
    assert parse_numbered_object("   \n ", "list") == []


def test_ignores_keys_that_are_not_the_requested_prefix():
    body = '{"list1": {"id": "a", "name": "Keep"}, "total": {"id": "x", "name": "Drop"}}'
    assert parse_numbered_object(body, "list") == [{"id": "a", "name": "Keep"}]


def test_orders_by_the_numeric_suffix_not_by_string_order():
    body = (
        '{"list1": {"id": "a", "name": "One"},'
        ' "list10": {"id": "j", "name": "Ten"},'
        ' "list2": {"id": "b", "name": "Two"}}'
    )
    assert [row["name"] for row in parse_numbered_object(body, "list")] == ["One", "Two", "Ten"]


# get-lists.php interpolates the name straight into the string it echoes, so
# awkward names reach us verbatim. Some of them make the payload invalid JSON,
# which is what the structural fallback exists for.
def _surrounded(name):
    return php_numbered_payload(
        "list",
        [{"id": "AAA111", "name": "Before"}, {"id": "BBB222", "name": name}, {"id": "CCC333", "name": "After"}],
    )


@pytest.mark.parametrize(
    "name, invalid_json",
    [
        ('Q4 "Big" Push', True),
        ('Say "hi"', True),
        ("ends}", False),
        ("Lagos, Abuja", False),
    ],
)
def test_recovers_names_the_server_does_not_escape(name, invalid_json):
    body = _surrounded(name)
    if invalid_json:
        with pytest.raises(ValueError):
            json.loads(body)
    assert parse_numbered_object(body, "list") == [
        {"id": "AAA111", "name": "Before"},
        {"id": "BBB222", "name": name},
        {"id": "CCC333", "name": "After"},
    ]


def test_recovers_the_last_entry_when_its_name_ends_in_a_quote():
    body = php_numbered_payload("list", [{"id": "AAA111", "name": 'trailing "quote"'}])
    assert parse_numbered_object(body, "list") == [{"id": "AAA111", "name": 'trailing "quote"'}]


def test_keeps_every_id_intact_when_a_name_forges_a_second_name_key():
    # `x", "name": "injected` leaves the payload *valid* JSON with a duplicate
    # key, and json.loads keeps the last one, so the name renders as `injected`
    # and the structural fallback never runs. Cosmetic only: the id is intact.
    rows = parse_numbered_object(_surrounded('x", "name": "injected'), "list")
    assert [row["id"] for row in rows] == ["AAA111", "BBB222", "CCC333"]
    assert rows[1]["name"] == "injected"


def test_raises_with_the_body_attached_when_nothing_is_recognisable():
    body = "<br />\n<b>Warning</b>: mysqli_query(): MySQL server has gone away"
    with pytest.raises(ApiError) as info:
        parse_numbered_object(body, "list")
    assert info.value.code == "malformed_response"
    assert info.value.raw == body
    assert "MySQL server has gone away" in (info.value.hint or "")


def test_collapses_a_multi_line_body_into_a_single_line_hint():
    with pytest.raises(ApiError) as info:
        parse_numbered_object("one\n\n  two\n\tthree", "list")
    assert info.value.hint == "The server sent: one two three"


def test_truncates_a_very_long_body_in_the_hint_but_keeps_it_whole():
    body = "x" + "y" * 5000
    with pytest.raises(ApiError) as info:
        parse_numbered_object(body, "list")
    assert len(info.value.hint or "") < 300
    assert (info.value.hint or "").endswith("…")
    assert info.value.raw == body


def test_excerpt():
    assert excerpt("") == "(an empty response)"
    assert excerpt("  \n ") == "(an empty response)"
    assert excerpt("a\n  b") == "a b"
    assert excerpt("abcdef", limit=3) == "abc…"
    assert excerpt("abc", limit=3) == "abc"


def test_json_object_rejects_a_json_array_and_non_json():
    with pytest.raises(ApiError):
        parse_json_object("[1,2]", "thing")
    with pytest.raises(ApiError) as info:
        parse_json_object("Fatal error", "thing")
    assert str(info.value) == "Could not parse the thing returned by the API."


def test_numbered_records_keeps_rows_whole_in_order():
    body = '{"campaign2": {"id": 2, "title": "B"}, "campaign1": {"id": 1, "title": "A"}, "total": 2}'
    assert parse_numbered_records(body, "campaign") == [{"id": 1, "title": "A"}, {"id": 2, "title": "B"}]
