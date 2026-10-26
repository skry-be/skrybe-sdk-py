"""Parsers for the API's response bodies.

``api/lists/get-lists.php`` and ``api/brands/get-brands.php`` build their
payload by string concatenation::

    $output .= '"list'.$i.'": { "id": "'.encrypt_val($id).'", "name": "'.$name.'" },'

Consequences we have to live with until those endpoints use json_encode():

- no Content-Type header
- entries are keyed ``list1``, ``list2``, ... rather than being an array
- the name is NOT escaped, so a list called ``Q4 "Big" Push`` emits invalid JSON

The id is safe to match on: encrypt_val() base64s and then substitutes
``/`` -> 892 and ``+`` -> 763 and strips ``=``, so it never contains a quote.
That gives a reliable structural anchor for the fallback parser.
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Tuple

from .errors import ApiError, excerpt


_DIGITS = re.compile(r"[0-9]+")


def _decode_object(text: str) -> "Dict[str, Any] | None":
    """Decode a JSON object; ``None`` for anything else, a JSON array included."""
    try:
        parsed = json.loads(text)
    except ValueError:
        return None
    return parsed if isinstance(parsed, dict) else None


def _malformed(what: str, body: str, trimmed: str) -> ApiError:
    # The body is the whole diagnosis here: usually a PHP warning or an
    # interstitial from something in front of the install. ``raw`` keeps the
    # untruncated version.
    return ApiError(
        "malformed_response",
        f"Could not parse the {what} returned by the API.",
        hint=f"The server sent: {excerpt(trimmed)}",
        raw=body,
    )


def _extract_by_structure(body: str, prefix: str) -> List[Dict[str, str]]:
    """Structural fallback for payloads ``json.loads`` rejects.

    The trailing lookahead is what makes an embedded quote survive: the lazy
    name match can only stop at a ``"`` that is followed by the closing brace
    of the entry AND either the next ``listN``/``brandN`` key or the end of
    the object.
    """
    p = re.escape(prefix)
    entry = re.compile(
        rf'"{p}\d+"\s*:\s*\{{\s*'
        rf'"id"\s*:\s*"([^"]*)"\s*,\s*'
        rf'"name"\s*:\s*"([\s\S]*?)"\s*\}}'
        rf'(?=\s*,\s*"{p}\d+"\s*:|\s*\}}\s*$)'
    )
    return [{"id": m.group(1), "name": m.group(2)} for m in entry.finditer(body)]


def parse_numbered_object(body: str, prefix: str) -> List[Dict[str, str]]:
    """Parse a ``{"list1": {...}, "list2": {...}}`` payload into an ordered list.

    ``prefix`` is the key prefix the endpoint uses: ``list`` or ``brand``.
    Raises :class:`ApiError` ``malformed_response`` if the body is neither
    valid JSON nor structurally recognisable.
    """
    trimmed = body.strip()
    if trimmed == "":
        return []

    # Happy path, and the path this takes once the endpoints use json_encode().
    parsed = _decode_object(trimmed)
    if parsed is not None:
        rows: List[Tuple[int, Dict[str, str]]] = []
        for index, (key, value) in enumerate(
            (k, v) for k, v in parsed.items() if k.startswith(prefix) and isinstance(v, dict)
        ):
            suffix = key[len(prefix):]
            sort = int(suffix) if _DIGITS.fullmatch(suffix) else index
            rows.append((sort, {"id": _str(value.get("id")), "name": _str(value.get("name"))}))
        # Stable, so equal keys keep the server's order.
        rows.sort(key=lambda r: r[0])
        return [row for _, row in rows]

    # Almost certainly an unescaped quote in a name.
    recovered = _extract_by_structure(trimmed, prefix)
    if recovered:
        return recovered

    raise _malformed(f"{prefix} payload", body, trimmed)


def _str(value: Any) -> str:
    return "" if value is None else str(value)


def parse_numbered_records(body: str, prefix: str) -> List[Dict[str, Any]]:
    """Parse a numbered payload from an endpoint that builds it with json_encode().

    Used for ``api/campaigns/get-campaigns.php``: rows are kept whole, in the
    order of their numeric suffix.
    """
    parsed = parse_json_object(body, f"{prefix} payload")
    key = re.compile(rf"^{re.escape(prefix)}(\d+)$")
    rows: List[Tuple[int, Dict[str, Any]]] = []
    for name, value in parsed.items():
        match = key.match(name)
        if match and isinstance(value, dict):
            rows.append((int(match.group(1)), value))
    rows.sort(key=lambda r: r[0])
    return [row for _, row in rows]


def parse_json_object(body: str, what: str) -> Dict[str, Any]:
    """Parse a body that must be a JSON object, e.g. ``api/campaigns/stats.php``.

    Anything else is almost always a PHP warning or a proxy page, so the body
    itself goes in the hint.
    """
    trimmed = body.strip()
    parsed = _decode_object(trimmed)
    if parsed is not None:
        return parsed
    raise _malformed(what, body, trimmed)
