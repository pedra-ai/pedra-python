"""Agent signup: get a Pedra API key for a person, with their say-so, without
having one yet. For agents with no browser in the loop (scripts, Claude Code,
a local MCP server).

1. :func:`request_access` — Pedra emails the person a confirmation link (valid
   30 min). A new account chooses a password there; an existing one just
   clicks "Allow". Nothing is created before the click.
2. :func:`wait_for_access` — polls until they approve (→ ``api_key``), decline,
   or the link expires.

Inbox confirmation is required, disposable email domains are refused, and
requests are rate-limited (HTTP 429, ``code == "rate_limited"``).

Example::

    from pedra import Pedra, request_access, wait_for_access

    req = request_access("ana@agency.com", agent_name="My script")
    print("Check your email to confirm.")
    res = wait_for_access(req.request_id)
    if res.approved:
        pedra = Pedra(res.api_key)
"""

import time
from typing import Optional

from .client import DEFAULT_BASE_URL, _build_ssl_context, _http_post
from .errors import PedraError
from .models import AccessRequest, AccessStatus

#: Per-request timeout (seconds) for the signup calls.
DEFAULT_ACCESS_TIMEOUT = 30.0


def _post(path: str, body: dict, base_url: str, timeout: float) -> dict:
    return _http_post(
        base_url.rstrip("/"),
        path,
        {k: v for k, v in body.items() if v is not None},
        timeout=timeout,
        ssl_context=_build_ssl_context(),
    )


def request_access(
    email: str,
    *,
    agent_name: Optional[str] = None,
    base_url: str = DEFAULT_BASE_URL,
    timeout: float = DEFAULT_ACCESS_TIMEOUT,
) -> AccessRequest:
    """Ask for an API key for ``email``. No API key needed.

    Pedra emails the person a link to confirm (new accounts set a password
    there). The response is the same whether or not the address already has
    an account. Tell the person to check their email, then call
    :func:`wait_for_access` with ``request_id``.

    Raises :class:`PedraAPIError` with ``status`` 400 (invalid email, or
    ``code == "disposable_email"``), 429 (``code == "rate_limited"``) or 503
    (``code == "unavailable"``).
    """
    if not isinstance(email, str) or not email.strip():
        raise PedraError("request_access: email is required")
    data = _post(
        "/agent_signup",
        {"email": email, "agentName": agent_name},
        base_url,
        timeout,
    )
    return AccessRequest(
        request_id=data.get("requestId", ""),
        status=data.get("status", "pending"),
        expires_at=data.get("expiresAt"),
        poll_after_seconds=data.get("pollAfterSeconds"),
        message=data.get("message"),
        raw=data,
    )


def get_access_status(
    request_id: str,
    *,
    base_url: str = DEFAULT_BASE_URL,
    timeout: float = DEFAULT_ACCESS_TIMEOUT,
) -> AccessStatus:
    """Check an access request once: ``pending``, ``approved`` (with
    ``api_key``), ``denied`` or ``expired``. After approval the key can be
    fetched for 15 minutes. An unknown ``request_id`` raises
    :class:`PedraAPIError` (HTTP 404)."""
    if not request_id:
        raise PedraError("get_access_status: request_id is required")
    data = _post("/agent_signup_status", {"requestId": request_id}, base_url, timeout)
    status = data.get("status")
    if status not in ("pending", "approved", "denied", "expired"):
        raise PedraError(f"Unexpected access status: {status!r}")
    credits = data.get("creditsRemaining")
    return AccessStatus(
        status=status,
        api_key=data.get("apiKey"),
        email=data.get("email"),
        new_account=data.get("newAccount"),
        plan=data.get("plan"),
        credits_remaining=int(credits) if credits is not None else None,
        app_url=data.get("appUrl"),
        note=data.get("note"),
        poll_after_seconds=data.get("pollAfterSeconds"),
        raw=data,
    )


def wait_for_access(
    request_id: str,
    *,
    interval: float = 5.0,
    timeout: float = 1800.0,
    base_url: str = DEFAULT_BASE_URL,
    request_timeout: float = DEFAULT_ACCESS_TIMEOUT,
) -> AccessStatus:
    """Poll :func:`get_access_status` until the request is no longer pending
    and return it: ``approved`` (with ``api_key``), ``denied`` or ``expired`` —
    a refusal is returned, not raised. Raises :class:`PedraError` if it is
    still pending after ``timeout`` seconds (default 30 min, the confirmation
    link's lifetime)."""
    deadline = time.monotonic() + timeout
    while True:
        res = get_access_status(request_id, base_url=base_url, timeout=request_timeout)
        if res.status != "pending":
            return res
        if time.monotonic() + interval > deadline:
            raise PedraError(
                f"Access request was still pending after {timeout}s. "
                "Ask the person to open the link in their email."
            )
        time.sleep(interval)
