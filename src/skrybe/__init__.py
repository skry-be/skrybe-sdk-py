"""The official Python SDK for the Skrybe email marketing API.

>>> from skrybe import Skrybe
>>> skrybe = Skrybe(api_key="...")
>>> skrybe.lists.list()
"""

from ._client import DEFAULT_BASE_URL, Skrybe
from ._version import VERSION
from .errors import (
    ApiError,
    AuthenticationError,
    ConnectionError,
    InvalidRequestError,
    RateLimitError,
    SkrybeError,
)
from .resources.campaigns import (
    ACTIVITY_TYPES,
    CAMPAIGN_STATUSES,
    MAX_ACTIVITY_PAGE,
    MAX_CAMPAIGNS_PAGE,
    MAX_TEST_EMAILS,
)
from .resources.emails import MAX_RECIPIENTS
from .resources.subscribers import MAX_SUBSCRIBERS_PAGE, SUBSCRIBER_STATUSES

__version__ = VERSION

__all__ = [
    "Skrybe",
    "DEFAULT_BASE_URL",
    "VERSION",
    "__version__",
    "SkrybeError",
    "AuthenticationError",
    "InvalidRequestError",
    "RateLimitError",
    "ConnectionError",
    "ApiError",
    "MAX_RECIPIENTS",
    "CAMPAIGN_STATUSES",
    "ACTIVITY_TYPES",
    "MAX_CAMPAIGNS_PAGE",
    "MAX_ACTIVITY_PAGE",
    "MAX_TEST_EMAILS",
    "SUBSCRIBER_STATUSES",
    "MAX_SUBSCRIBERS_PAGE",
]
