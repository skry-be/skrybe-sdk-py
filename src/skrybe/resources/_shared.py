from __future__ import annotations

from typing import Iterable, List, Optional, Union

Ids = Union[str, int, Iterable[Union[str, int]]]


def join_ids(ids: Optional[Ids]) -> Optional[str]:
    """Comma-joined, or None for an empty or missing list so the field is not sent.

    A single id is accepted too, rather than having a string's characters
    joined one by one.
    """
    if ids is None:
        return None
    if isinstance(ids, (str, int)):
        return str(ids) if ids != "" else None
    joined = ",".join(str(i) for i in ids)
    return joined or None


def as_list(values: Union[str, Iterable[str], None]) -> List[str]:
    """A list of addresses, accepting one address given as a plain string."""
    if values is None:
        return []
    if isinstance(values, str):
        return [values]
    return list(values)


def flag(value: object) -> Optional[int]:
    """``1`` when set, so a false flag leaves the field out rather than sending ``0``."""
    return 1 if value else None
