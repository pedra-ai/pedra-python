"""Exceptions raised by the Pedra SDK."""

from typing import Any, Optional


class PedraError(Exception):
    """Base class for every error raised by the SDK.

    Catch this to handle any Pedra-originated failure (network, timeout, bad
    input, or an API error).
    """


class PedraAPIError(PedraError):
    """Raised when the API returns an error.

    ``status`` is the HTTP status code. Note: the Pedra API keeps long requests
    alive with a heartbeat, so a generation that runs long and *then* fails
    comes back as HTTP 200 with an ``{"error": ...}`` body — in that case
    ``status`` is 200 but the call still raises this error. ``body`` is the
    parsed JSON response when available, and ``code`` its machine-readable
    ``code`` field when it has one (e.g. ``"upload_limit"`` or
    ``"upload_link_limit"`` on HTTP 429, ``"rate_limited"``,
    ``"disposable_email"``, ``"unavailable"``, ``"tour_exists"``).
    """

    def __init__(
        self,
        message: str,
        status: Optional[int] = None,
        body: Any = None,
    ) -> None:
        super().__init__(message)
        self.status = status
        self.body = body
        code = body.get("code") if isinstance(body, dict) else None
        self.code: Optional[str] = code if isinstance(code, str) else None
