"""Shared httpx client factory with tenacity retry. Mirrors recruiter/http.py."""

from __future__ import annotations

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from micar.config import get_settings


def build_client(*, base_url: str | None = None, headers: dict[str, str] | None = None) -> httpx.Client:
    settings = get_settings()
    return httpx.Client(
        base_url=base_url or "",
        headers=headers or {},
        timeout=settings.http_timeout_seconds,
    )


def retry_http():
    """Decorator factory: retry on transient httpx errors."""
    settings = get_settings()
    return retry(
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.NetworkError)),
        stop=stop_after_attempt(settings.http_max_retries),
        wait=wait_exponential(multiplier=0.5, min=0.5, max=8),
        reraise=True,
    )
