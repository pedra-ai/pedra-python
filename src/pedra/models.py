"""Typed response models returned by the SDK."""

from dataclasses import dataclass, field
from typing import Any, List, Optional


@dataclass
class ImageResponse:
    """Response from any image-generation endpoint.

    The raw API returns ``output`` as either a list or a single object
    depending on the endpoint; the SDK normalizes that into ``urls`` (and the
    convenience ``url`` for the first result).
    """

    message: Optional[str]
    urls: List[str]
    raw: Any = field(repr=False, default=None)

    @property
    def url(self) -> Optional[str]:
        """The first generated asset URL, or ``None`` if there were none."""
        return self.urls[0] if self.urls else None


@dataclass
class VideoResponse:
    message: Optional[str]
    video_id: str
    video_url: str
    raw: Any = field(repr=False, default=None)


@dataclass
class CreditsResponse:
    plan: str
    credits_remaining: int
    raw: Any = field(repr=False, default=None)


@dataclass
class FeedbackResponse:
    message: Optional[str]
    credited_back: Optional[bool]
    raw: Any = field(repr=False, default=None)
