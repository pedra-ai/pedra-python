"""Typed response models returned by the SDK."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Literal, Optional, TypedDict


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
    #: Voices offered per language; a ``voice_id`` is only valid for the
    #: language it is listed under.
    voices_by_language: List[Any] = field(default_factory=list)
    raw: Any = field(repr=False, default=None)


@dataclass
class PropertiesResponse:
    properties: List[Any]
    raw: Any = field(repr=False, default=None)


@dataclass
class PropertyImagesResponse:
    property_id: str
    name: Optional[str]
    images: List[Any]
    raw: Any = field(repr=False, default=None)


@dataclass
class PropertyResponse:
    message: Optional[str]
    property_id: str
    app_url: Optional[str] = None
    raw: Any = field(repr=False, default=None)


@dataclass
class AddImagesResponse:
    message: Optional[str]
    property_id: str
    added: List[Any]
    failed: List[Any]
    app_url: Optional[str] = None
    #: ``"360"`` when 360° photos were added.
    type: Optional[str] = None
    raw: Any = field(repr=False, default=None)


# --- virtual tours -----------------------------------------------------------

#: Which images of a property: regular photos or 360° photos.
PropertyImageType = Literal["photo", "360"]
#: Language of the tour page and of the AI room names.
TourLanguage = Literal["en", "es", "fr", "de", "it", "pt"]
#: How rooms get connected: ``"sequential"`` (default), ``"smart"``, ``"none"``.
TourLinking = Literal["sequential", "smart", "none"]
#: A tour builds in the background: poll until ``"ready"`` or ``"failed"``.
TourStatus = Literal["processing", "ready", "failed"]


class TourSceneInput(TypedDict, total=False):
    """One room to create or append. Pass exactly one of ``image_url`` /
    ``image_id`` (camelCase keys work too)."""

    #: A 360° photo (2:1 equirectangular): public https URL or ``data:`` URI.
    image_url: str
    #: Id of a 360° photo already in the property.
    image_id: str
    #: Room name shown in the tour. Omit and AI names the room.
    name: str


class TourLinkInput(TypedDict, total=False):
    """A one-direction navigation point, for ``update_virtual_tour(links=...)``."""

    from_scene_id: str
    to_scene_id: str
    #: Horizontal angle in the from-scene, -180..180 (0 = centre of the photo).
    yaw: float
    #: Vertical angle, -90..90 (0 = horizon, the default).
    pitch: float


@dataclass
class VirtualTour:
    """A virtual tour, as returned by the tour endpoints.

    Nested items (``scenes``, ``links``, ``settings``, ``progress``,
    ``failed_scenes``) are the API's dicts, with camelCase keys (e.g.
    ``scene["sceneId"]``, ``link["fromSceneId"]``).
    """

    tour_id: str
    property_id: Optional[str]
    name: Optional[str]
    #: ``"processing"``, ``"ready"`` or ``"failed"``.
    status: str
    #: Public, shareable tour page.
    tour_url: str
    #: ``<iframe>`` snippet to embed the tour on a website.
    embed_code: str
    app_url: Optional[str] = None
    #: ``False`` on the free plan: the public link shows an upgrade page.
    shareable: Optional[bool] = None
    shareable_note: Optional[str] = None
    scene_count: Optional[int] = None
    link_count: Optional[int] = None
    cover_image_url: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    #: While processing: ``{"stage": ..., "done"?: n, "total"?: n}``.
    progress: Optional[Dict[str, Any]] = None
    #: Why the build failed (``status == "failed"``). Failed builds cost nothing.
    error: Optional[str] = None
    #: Why the last ``add_virtual_tour_scenes`` failed (the tour stays ready).
    last_error: Optional[str] = None
    failed_scenes: Optional[List[Any]] = None
    scenes: Optional[List[Any]] = None
    links: Optional[List[Any]] = None
    settings: Optional[Dict[str, Any]] = None
    # create / add_virtual_tour_scenes only:
    message: Optional[str] = None
    linking: Optional[str] = None
    credits_cost: Optional[int] = None
    estimated_seconds: Optional[int] = None
    added_scenes: Optional[List[Any]] = None
    raw: Any = field(repr=False, default=None)


@dataclass
class VirtualToursResponse:
    #: Tour summaries (newest first, max 100), as camelCase dicts.
    tours: List[Any]
    raw: Any = field(repr=False, default=None)


@dataclass
class DeleteVirtualTourResponse:
    message: Optional[str]
    tour_id: str
    raw: Any = field(repr=False, default=None)


@dataclass
class UploadLinkResponse:
    message: Optional[str]
    #: No-login page (phone or computer, 24 h) to drop photos into the property.
    upload_url: str
    property_id: str
    property_name: Optional[str] = None
    #: What the page accepts: ``"any"`` (photos and 360° photos) or ``"360"``.
    type: Optional[str] = None
    expires_at: Optional[str] = None
    #: Most files one link takes (100).
    max_files: Optional[int] = None
    app_url: Optional[str] = None
    raw: Any = field(repr=False, default=None)


@dataclass
class AccessRequest:
    """Response from :func:`pedra.request_access`."""

    #: Pass to :func:`pedra.get_access_status` / :func:`pedra.wait_for_access`.
    #: Keep it private: it redeems the API key.
    request_id: str
    status: str = "pending"
    expires_at: Optional[str] = None
    #: Suggested delay before the first status check (5).
    poll_after_seconds: Optional[int] = None
    message: Optional[str] = None
    raw: Any = field(repr=False, default=None)


@dataclass
class AccessStatus:
    """Response from :func:`pedra.get_access_status`.

    ``status`` is ``"pending"``, ``"approved"``, ``"denied"`` or ``"expired"``.
    Only an approved status carries ``api_key`` and the account fields.
    ``note`` appears when the account has no credits left (new accounts start
    with the free trial): the person can get credits with a plan.
    """

    status: str
    api_key: Optional[str] = field(repr=False, default=None)
    email: Optional[str] = None
    new_account: Optional[bool] = None
    plan: Optional[str] = None
    credits_remaining: Optional[int] = None
    app_url: Optional[str] = None
    note: Optional[str] = None
    poll_after_seconds: Optional[int] = None
    raw: Any = field(repr=False, default=None)

    @property
    def approved(self) -> bool:
        return self.status == "approved"
