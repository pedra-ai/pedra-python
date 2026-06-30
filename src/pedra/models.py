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


@dataclass
class ScriptResponse:
    message: Optional[str]
    script: str
    raw: Any = field(repr=False, default=None)


@dataclass
class VoiceResponse:
    message: Optional[str]
    audio_id: str
    audio_url: str
    alignment_url: Optional[str] = None
    duration: Optional[int] = None
    raw: Any = field(repr=False, default=None)


@dataclass
class MusicLibraryResponse:
    tracks: List[Any]
    variants_per_track: int
    default_track: str
    voice_languages: List[str]
    raw: Any = field(repr=False, default=None)


@dataclass
class ProjectsResponse:
    projects: List[Any]
    raw: Any = field(repr=False, default=None)


@dataclass
class ProjectImagesResponse:
    project_id: str
    name: Optional[str]
    images: List[Any]
    raw: Any = field(repr=False, default=None)


@dataclass
class ProjectResponse:
    message: Optional[str]
    project_id: str
    app_url: Optional[str] = None
    raw: Any = field(repr=False, default=None)


@dataclass
class AddImagesResponse:
    message: Optional[str]
    project_id: str
    added: List[Any]
    failed: List[Any]
    app_url: Optional[str] = None
    raw: Any = field(repr=False, default=None)
