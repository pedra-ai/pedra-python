"""Synchronous client for the Pedra API."""

import base64
import json
import os
import ssl
import time
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional, Sequence, Union

from .errors import PedraAPIError, PedraError
from .models import (
    AccessRequest,
    AccessStatus,
    AddImagesResponse,
    CreditsResponse,
    DeleteVirtualTourResponse,
    FeedbackResponse,
    ImageResponse,
    MusicLibraryResponse,
    PropertyImagesResponse,
    PropertyResponse,
    PropertiesResponse,
    ScriptResponse,
    UploadLinkResponse,
    VideoResponse,
    VirtualTour,
    VirtualToursResponse,
    VoiceResponse,
)

DEFAULT_BASE_URL = "https://app.pedra.ai/api"
# createVideo blocks server-side until the video is rendered (up to ~10 min).
DEFAULT_TIMEOUT = 600.0

# add_images_to_property with type "360" takes at most 10 per call, and the API
# parses bodies up to 50 MB; stay under it with room for the JSON around it.
MAX_PANORAMAS_PER_CALL = 10
DEFAULT_MAX_REQUEST_BYTES = 45 * 1024 * 1024
_PANORAMA_MIME_BY_EXT = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
}

PathLike = Union[str, "os.PathLike[str]"]


def _build_ssl_context() -> ssl.SSLContext:
    """Build a TLS context backed by certifi's CA bundle.

    Stock python.org builds on macOS (and some minimal Linux images) ship no
    trusted-root bundle, so ``urllib`` raises ``CERTIFICATE_VERIFY_FAILED`` for
    every HTTPS request. Pinning certifi makes the client work out of the box.
    If certifi is somehow missing, fall back to the system default context.
    """
    try:
        import certifi

        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()


def _to_camel(key: str) -> str:
    """Convert a snake_case key to camelCase (the API's wire format)."""
    head, *tail = key.split("_")
    return head + "".join(word[:1].upper() + word[1:] for word in tail)


def _camelize(value: Any) -> Any:
    """Recursively convert dict keys from snake_case to camelCase.

    Only keys are transformed; string values (URLs, prompts, labels) are left
    untouched. This lets callers use Pythonic snake_case everywhere while the
    request body matches the camelCase the API expects.
    """
    if isinstance(value, dict):
        return {_to_camel(k): _camelize(v) for k, v in value.items() if v is not None}
    if isinstance(value, (list, tuple)):
        return [_camelize(v) for v in value]
    return value


def _parse_json(text: str) -> Any:
    # json.loads tolerates the leading whitespace the heartbeat prepends.
    if not text or not text.strip():
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def _http_post(
    base_url: str,
    path: str,
    body: Dict[str, Any],
    *,
    timeout: float,
    ssl_context: ssl.SSLContext,
    tour: bool = False,
) -> Dict[str, Any]:
    """POST a JSON body to the Pedra API and return the parsed response.

    ``tour``: the response is a tour, whose ``error`` field is why a build
    failed (HTTP 200, status "failed") — data, not a failed request.
    """
    payload = json.dumps(body).encode("utf-8")
    request = urllib.request.Request(
        f"{base_url}{path}",
        data=payload,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )

    try:
        with urllib.request.urlopen(
            request, timeout=timeout, context=ssl_context
        ) as response:
            status = response.getcode()
            text = response.read().decode("utf-8")
    except urllib.error.HTTPError as err:  # non-2xx
        text = err.read().decode("utf-8", errors="replace")
        data = _parse_json(text)
        message = (
            (data.get("error") or data.get("message"))
            if isinstance(data, dict)
            else None
        ) or f"Request to {path} failed with status {err.code}"
        raise PedraAPIError(message, status=err.code, body=data) from None
    except urllib.error.URLError as err:
        raise PedraError(f"Network error calling {path}: {err.reason}") from err
    except TimeoutError as err:
        raise PedraError(f"Request to {path} timed out after {timeout}s") from err

    data = _parse_json(text)
    if data is None:
        raise PedraError(f"Could not parse the response from {path}")

    # Heartbeat caveat: a request that runs long and then fails returns HTTP
    # 200 with an ``{"error": ...}`` body (the 200 header was already sent).
    if isinstance(data, dict) and data.get("error"):
        if not (tour and "tourId" in data and "status" in data):
            raise PedraAPIError(str(data["error"]), status=status, body=data)

    return data


class Pedra:
    """Client for the Pedra API.

    Every method is a synchronous, blocking call that returns the final
    asset URL(s) — there are no client-side job IDs to poll (the API keeps long
    requests alive with a heartbeat).

    Example::

        from pedra import Pedra

        pedra = Pedra("YOUR_API_KEY")
        result = pedra.furnish(
            image_url="https://example.com/empty-room.jpg",
            room_type="Living room",
            style="Minimalist",
        )
        print(result.url)
    """

    # --- agent signup (no API key needed) -----------------------------------

    @staticmethod
    def request_access(email: str, **kwargs: Any) -> "AccessRequest":
        """Same as :func:`pedra.request_access` (no API key needed)."""
        from .access import request_access

        return request_access(email, **kwargs)

    @staticmethod
    def get_access_status(request_id: str, **kwargs: Any) -> "AccessStatus":
        """Same as :func:`pedra.get_access_status` (no API key needed)."""
        from .access import get_access_status

        return get_access_status(request_id, **kwargs)

    @staticmethod
    def wait_for_access(request_id: str, **kwargs: Any) -> "AccessStatus":
        """Same as :func:`pedra.wait_for_access` (no API key needed)."""
        from .access import wait_for_access

        return wait_for_access(request_id, **kwargs)

    def __init__(
        self,
        api_key: Optional[str] = None,
        *,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> None:
        key = api_key or os.environ.get("PEDRA_API_KEY")
        if not key:
            raise PedraError(
                "A Pedra API key is required. Pass it to Pedra(api_key=...) or "
                "set the PEDRA_API_KEY environment variable. No account yet? Get a "
                "key with pedra.request_access(email) (the person confirms by email)."
            )
        self.api_key = key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._ssl_context = _build_ssl_context()

    # --- endpoints -----------------------------------------------------------

    def enhance(
        self, image_url: str, *, preserve_original_framing: Optional[bool] = None
    ) -> ImageResponse:
        """Enhance an image (lighting, color, sharpness)."""
        return self._image(
            self._post(
                "/enhance",
                image_url=image_url,
                preserve_original_framing=preserve_original_framing,
            )
        )

    def enhance_and_correct_perspective(
        self, image_url: str, *, preserve_original_framing: Optional[bool] = None
    ) -> ImageResponse:
        """Enhance an image and correct its perspective."""
        return self._image(
            self._post(
                "/enhance_and_correct_perspective",
                image_url=image_url,
                preserve_original_framing=preserve_original_framing,
            )
        )

    def empty(self, image_url: str) -> ImageResponse:
        """Empty a room — remove all furniture and objects. (``/empty_room``)"""
        return self._image(self._post("/empty_room", image_url=image_url))

    def furnish(
        self,
        image_url: str,
        *,
        room_type: Optional[str] = None,
        style: Optional[str] = None,
        creativity: Optional[str] = None,
    ) -> ImageResponse:
        """Virtually stage / furnish a room.

        ``creativity`` is deprecated and ignored by the API since September 2026:
        there is one level, which keeps walls, doors, windows and the camera angle.
        """
        return self._image(
            self._post(
                "/furnish",
                image_url=image_url,
                room_type=room_type,
                style=style,
                creativity=creativity,
            )
        )

    def renovation(
        self,
        image_url: str,
        *,
        style: Optional[str] = None,
        creativity: Optional[str] = None,
        furnish: Any = None,
        room_type: Optional[str] = None,
    ) -> ImageResponse:
        """Renovate a space. ``furnish`` accepts a bool or the explicit string
        ("With furniture" / "Empty" / "Auto").

        ``creativity`` is deprecated and ignored by the API since September 2026:
        there is one level, which keeps walls, doors, windows and the camera angle.
        """
        return self._image(
            self._post(
                "/renovation",
                image_url=image_url,
                style=style,
                creativity=creativity,
                furnish=furnish,
                room_type=room_type,
            )
        )

    def edit_via_prompt(self, image_url: str, prompt: str) -> ImageResponse:
        """Edit an image from a natural-language prompt. (``/edit_via_prompt``)"""
        return self._image(
            self._post("/edit_via_prompt", image_url=image_url, prompt=prompt)
        )

    def sky(self, image_url: str, *, sky_style: Optional[str] = None) -> ImageResponse:
        """Replace a dull/overcast sky with a clear blue one. (``/sky_blue``)"""
        return self._image(
            self._post("/sky_blue", image_url=image_url, sky_style=sky_style)
        )

    def remove(self, image_url: str, mask_url: str) -> ImageResponse:
        """Remove an object using a mask. (``/remove_object``)"""
        return self._image(
            self._post("/remove_object", image_url=image_url, mask_url=mask_url)
        )

    def blur(self, image_url: str, objects_to_blur: Any) -> ImageResponse:
        """Blur objects (e.g. faces, license plates)."""
        return self._image(
            self._post("/blur", image_url=image_url, objects_to_blur=objects_to_blur)
        )

    def create_video(
        self,
        images: List[Dict[str, Any]],
        *,
        music: Optional[Dict[str, Any]] = None,
        voice: Optional[Dict[str, Any]] = None,
        branding: Optional[Dict[str, Any]] = None,
        ending_title: Optional[str] = None,
        ending_subtitle: Optional[str] = None,
        is_vertical: Optional[bool] = None,
        property_characteristics: Optional[List[Dict[str, Any]]] = None,
    ) -> VideoResponse:
        """Create a property video from a list of images.

        Blocks server-side (up to ~10 min) and returns the finished video URL
        inline. Each image dict accepts snake_case keys (``image_url``,
        ``effect``, ``second_image_url``, ``subtitle``, ``title``,
        ``watermark``, ``characteristics``). (``/create_video``)
        """
        data = self._post(
            "/create_video",
            images=images,
            music=music,
            voice=voice,
            branding=branding,
            ending_title=ending_title,
            ending_subtitle=ending_subtitle,
            is_vertical=is_vertical,
            property_characteristics=property_characteristics,
        )
        return VideoResponse(
            message=data.get("message"),
            video_id=data.get("videoId", ""),
            video_url=data.get("videoUrl", ""),
            raw=data,
        )

    def update_video(
        self,
        video_id: str,
        *,
        images: Optional[List[Dict[str, Any]]] = None,
        music: Optional[Dict[str, Any]] = None,
        voice: Optional[Dict[str, Any]] = None,
        branding: Optional[Dict[str, Any]] = None,
        ending_title: Optional[str] = None,
        ending_subtitle: Optional[str] = None,
        is_vertical: Optional[bool] = None,
        property_characteristics: Optional[List[Dict[str, Any]]] = None,
    ) -> VideoResponse:
        """Edit an existing video without re-rendering unchanged clips.

        Only new/changed photos re-animate (and cost credits); reordering,
        music, voice, branding and text re-stitch for free. Omit ``images`` to
        change only audio/text/branding while keeping the timeline; omit
        ``music``/``voice``/``branding``/ending text to leave them unchanged.
        Blocks until rendered and returns the new video URL. (``/update_video``)
        """
        data = self._post(
            "/update_video",
            video_id=video_id,
            images=images,
            music=music,
            voice=voice,
            branding=branding,
            ending_title=ending_title,
            ending_subtitle=ending_subtitle,
            is_vertical=is_vertical,
            property_characteristics=property_characteristics,
        )
        return VideoResponse(
            message=data.get("message"),
            video_id=data.get("videoId", video_id),
            video_url=data.get("videoUrl", ""),
            raw=data,
        )

    def generate_voice_script(
        self,
        *,
        images: Optional[List[Any]] = None,
        property_characteristics: Optional[List[Dict[str, Any]]] = None,
        language: Optional[str] = None,
    ) -> ScriptResponse:
        """Write a voiceover script from photos (and optional property facts).

        GPT-4o vision reads the images so the script reflects what's shown.
        ``images`` accepts URL strings or ``{"image_url": ...}`` dicts. Feed the
        result to :meth:`generate_voice`. (``/generate_voice_script``)
        """
        data = self._post(
            "/generate_voice_script",
            images=images,
            property_characteristics=property_characteristics,
            language=language,
        )
        return ScriptResponse(
            message=data.get("message"),
            script=data.get("script", ""),
            raw=data,
        )

    def generate_voice(
        self,
        text: str,
        *,
        language: Optional[str] = None,
        voice_id: Optional[str] = None,
    ) -> VoiceResponse:
        """Render a voiceover from a script via TTS.

        Returns an ``audio_id`` to pass as a video's ``voice={"audio_id": ...}``
        (which also drives synced subtitles). Pass ``voice_id`` to choose who
        narrates -- see :meth:`music_library`'s ``voices_by_language``. A voice
        is only valid for the language it is listed under.
        (``/generate_voice``)
        """
        data = self._post(
            "/generate_voice", text=text, language=language, voice_id=voice_id
        )
        return VoiceResponse(
            message=data.get("message"),
            audio_id=data.get("audioId", ""),
            audio_url=data.get("audioUrl", ""),
            alignment_url=data.get("alignmentUrl"),
            duration=data.get("duration"),
            raw=data,
        )

    def music_library(self) -> MusicLibraryResponse:
        """List the background-music catalog and voice languages. Read-only.

        Returns the valid ``music`` ``track`` values (genre keys) with labels.
        (``/music_library``)
        """
        data = self._post("/music_library")
        return MusicLibraryResponse(
            tracks=data.get("tracks", []),
            variants_per_track=int(data.get("variantsPerTrack", 0) or 0),
            default_track=data.get("defaultTrack", ""),
            voice_languages=data.get("voiceLanguages", []),
            voices_by_language=data.get("voicesByLanguage", []),
            raw=data,
        )

    def list_properties(self) -> PropertiesResponse:
        """List the account's properties (id, name, photo count, appUrl). Use it to
        find photos already in the account. (``/list_properties``)"""
        data = self._post("/list_properties")
        return PropertiesResponse(properties=data.get("properties", []), raw=data)

    def list_property_images(
        self, property_id: str, *, type: Optional[str] = None
    ) -> PropertyImagesResponse:
        """List a property's photos as public URLs, ready to pass to
        :meth:`create_video` or the edit methods. Pass ``type="360"`` to list
        its 360° photos instead (their ``imageId``s are the scenes of a virtual
        tour). (``/list_property_images``)"""
        data = self._post("/list_property_images", property_id=property_id, type=type)
        return PropertyImagesResponse(
            property_id=data.get("propertyId", property_id),
            name=data.get("name"),
            images=data.get("images", []),
            raw=data,
        )

    def create_property(self, *, name: Optional[str] = None) -> PropertyResponse:
        """Create a property. Returns its id and an ``app_url`` to open it in Pedra
        (the way to add brand-new local photos). (``/create_property``)"""
        data = self._post("/create_property", name=name)
        return PropertyResponse(
            message=data.get("message"),
            property_id=data.get("propertyId", ""),
            app_url=data.get("appUrl"),
            raw=data,
        )

    def add_images_to_property(
        self, property_id: str, image_urls: List[str], *, type: Optional[str] = None
    ) -> AddImagesResponse:
        """Add photos to a property by URL — the server fetches and stores each one,
        so any public https image URL (or ``data:`` URI) works. Pass
        ``type="360"`` for 360° photos (max 10 per call), which can then become
        a virtual tour. For 360° files on disk, see :meth:`add_local_panoramas`.
        Every stored image counts toward the daily upload limit (30 free, 500
        paid, reset at midnight UTC); over it the whole call is refused with
        :class:`PedraAPIError` status 429, ``code == "upload_limit"``.
        (``/add_images_to_property``)"""
        data = self._post(
            "/add_images_to_property",
            property_id=property_id,
            image_urls=image_urls,
            type=type,
        )
        return AddImagesResponse(
            message=data.get("message"),
            property_id=data.get("propertyId", property_id),
            added=data.get("added", []),
            failed=data.get("failed", []),
            app_url=data.get("appUrl"),
            type=data.get("type"),
            raw=data,
        )

    def add_local_panoramas(
        self,
        property_id: str,
        paths: Sequence[PathLike],
        *,
        max_request_bytes: int = DEFAULT_MAX_REQUEST_BYTES,
    ) -> AddImagesResponse:
        """Upload 360° photo files from local disk into a property.

        Each file is base64-encoded into a ``data:`` URI and sent with
        :meth:`add_images_to_property` (``type="360"``), in order, in batches
        that respect the API's 10-per-call and 50 MB body limits. Files are
        added in the order given, which is the order
        ``create_virtual_tour(property_id=...)`` uses for the rooms.

        Files that can't be sent (missing, not JPEG/PNG/WebP, or too large to
        send inline — over ~33 MB) and photos the API rejects (e.g. not 2:1) are
        reported in ``failed`` rather than raised; each entry carries its
        ``path``. For very large files use :meth:`create_upload_link`.
        """
        if not property_id:
            raise PedraError("add_local_panoramas: property_id is required")
        if isinstance(paths, (str, bytes)) or not paths:
            raise PedraError("add_local_panoramas: pass a list of file paths")

        added: List[Any] = []
        failed: List[Any] = []
        app_url: Optional[str] = None

        # Plan batches from file sizes, so only one batch is held in memory.
        batches: List[List[Any]] = []
        current: List[Any] = []
        current_bytes = 0
        for raw_path in paths:
            path = os.fspath(raw_path)
            ext = os.path.splitext(path)[1].lower()
            mime = _PANORAMA_MIME_BY_EXT.get(ext)
            if not mime:
                failed.append(
                    {
                        "url": path,
                        "path": path,
                        "error": f'Unsupported file type "{ext or "(none)"}": '
                        "a 360° photo must be JPEG, PNG or WebP",
                    }
                )
                continue
            try:
                size = os.path.getsize(path)
            except OSError as err:
                failed.append(
                    {"url": path, "path": path, "error": f"Could not read file: {err}"}
                )
                continue
            encoded = len(f"data:{mime};base64,") + -(-size // 3) * 4
            if encoded > max_request_bytes:
                limit_mb = max_request_bytes * 3 // 4 // (1024 * 1024)
                failed.append(
                    {
                        "url": path,
                        "path": path,
                        "error": f"File is {size / 1024 / 1024:.1f} MB, too large to "
                        f"send inline (limit ~{limit_mb} MB). Use create_upload_link() "
                        "and upload it on that page instead.",
                    }
                )
                continue
            if len(current) >= MAX_PANORAMAS_PER_CALL or (
                current and current_bytes + encoded > max_request_bytes
            ):
                batches.append(current)
                current, current_bytes = [], 0
            current.append((path, mime))
            current_bytes += encoded
        if current:
            batches.append(current)

        # Sequential calls keep the upload order across batches.
        for batch in batches:
            image_urls: List[str] = []
            sent: List[str] = []
            for path, mime in batch:
                try:
                    with open(path, "rb") as fh:
                        encoded_str = base64.b64encode(fh.read()).decode("ascii")
                except OSError as err:
                    failed.append(
                        {"url": path, "path": path, "error": f"Could not read file: {err}"}
                    )
                    continue
                image_urls.append(f"data:{mime};base64,{encoded_str}")
                sent.append(path)
            if not image_urls:
                continue
            res = self.add_images_to_property(property_id, image_urls, type="360")
            app_url = res.app_url or app_url
            # The API reports added/failed in input order but separately, so a
            # file is only matched to its result when the batch didn't mix them.
            exact = not res.failed or not res.added
            for i, item in enumerate(res.added):
                added.append({**item, "path": sent[i]} if exact else dict(item))
            for i, item in enumerate(res.failed):
                if exact:
                    failed.append({**item, "url": sent[i], "path": sent[i]})
                else:
                    failed.append({**item, "url": "one of: " + ", ".join(sent)})

        message = f"Added {len(added)} 360° photo(s)"
        if failed:
            message += f", {len(failed)} failed"
        return AddImagesResponse(
            message=message,
            property_id=property_id,
            added=added,
            failed=failed,
            app_url=app_url,
            type="360",
            raw=None,
        )

    # --- virtual tours -------------------------------------------------------

    def create_virtual_tour(
        self,
        scenes: Optional[List[Any]] = None,
        *,
        image_urls: Optional[List[str]] = None,
        property_id: Optional[str] = None,
        name: Optional[str] = None,
        linking: Optional[str] = None,
        language: Optional[str] = None,
    ) -> VirtualTour:
        """Build a hosted 360° virtual tour; AI names the rooms and places the
        door-to-door navigation points.

        ``scenes`` are the rooms in walking order: dicts with ``image_url`` (a
        2:1 360° photo URL or ``data:`` URI) or ``image_id`` (a 360° photo
        already in the property), plus an optional ``name``; a plain string is
        an image URL. Or pass ``image_urls``, or only ``property_id`` to use
        every 360° photo in that property in upload order.

        ``linking``: ``"sequential"`` (default, ``max(3, ceil(rooms/3))``
        credits), ``"smart"`` (AI finds which rooms connect; 5-160 credits) or
        ``"none"`` (free). ``language``: ``en`` ``es`` ``fr`` ``de`` ``it``
        ``pt``.

        Returns immediately with ``status == "processing"`` — poll
        :meth:`get_virtual_tour` or use :meth:`wait_for_virtual_tour`. One tour
        per property. (``/create_virtual_tour``)
        """
        data = self._post(
            "/create_virtual_tour",
            _tour=True,
            scenes=scenes,
            image_urls=image_urls,
            property_id=property_id,
            name=name,
            linking=linking,
            language=language,
        )
        return self._tour(data)

    def get_virtual_tour(self, tour_id: str) -> VirtualTour:
        """Get a tour: status (``processing`` / ``ready`` / ``failed`` with the
        reason in ``error``), share link, embed code, scenes and links. A failed
        build is returned, not raised — check ``status``. (``/get_virtual_tour``)"""
        return self._tour(self._post("/get_virtual_tour", _tour=True, tour_id=tour_id))

    def list_virtual_tours(
        self, *, property_id: Optional[str] = None
    ) -> VirtualToursResponse:
        """List the account's tours, newest first (max 100), optionally only one
        property's. (``/list_virtual_tours``)"""
        data = self._post("/list_virtual_tours", property_id=property_id)
        return VirtualToursResponse(tours=data.get("tours", []), raw=data)

    def update_virtual_tour(
        self,
        tour_id: str,
        *,
        name: Optional[str] = None,
        scene_names: Optional[Dict[str, str]] = None,
        scene_order: Optional[List[str]] = None,
        remove_scenes: Optional[List[str]] = None,
        links: Optional[List[Dict[str, Any]]] = None,
        navigation_style: Optional[str] = None,
        navigation_size: Optional[str] = None,
        show_labels: Optional[bool] = None,
        language: Optional[str] = None,
    ) -> VirtualTour:
        """Change a tour in place. Free, instant, validated all or nothing.

        ``scene_names`` is ``{scene_id: "Kitchen"}``; ``scene_order`` lists every
        scene id once (the first opens the tour); ``remove_scenes`` takes rooms
        out (the photos stay in the property); ``links`` REPLACES all
        navigation links (``{"from_scene_id", "to_scene_id", "yaw", "pitch"?}``,
        one direction each); ``navigation_style`` is ``"white"``/``"blue"``,
        ``navigation_size`` ``"small"``/``"medium"``/``"large"``. Returns the
        full updated tour. (``/update_virtual_tour``)
        """
        data = self._post(
            "/update_virtual_tour",
            _tour=True,
            # Keys are scene ids, not field names: sent as-is.
            _raw={"sceneNames": scene_names} if scene_names is not None else None,
            tour_id=tour_id,
            name=name,
            scene_order=scene_order,
            remove_scenes=remove_scenes,
            links=links,
            navigation_style=navigation_style,
            navigation_size=navigation_size,
            show_labels=show_labels,
            language=language,
        )
        return self._tour(data)

    def add_virtual_tour_scenes(
        self,
        tour_id: str,
        scenes: List[Any],
        *,
        linking: Optional[str] = None,
    ) -> VirtualTour:
        """Append rooms to a tour (same scene shape as :meth:`create_virtual_tour`).

        ``linking="sequential"`` (default) links only the new stretch and costs
        ``max(3, ceil(new_rooms/3))`` credits; ``"none"`` is free. Asynchronous:
        the tour stays live; poll until it's ``"ready"`` again (a failed append
        leaves it as it was, with ``last_error``). (``/add_virtual_tour_scenes``)
        """
        data = self._post(
            "/add_virtual_tour_scenes",
            _tour=True,
            tour_id=tour_id,
            scenes=scenes,
            linking=linking,
        )
        return self._tour(data)

    def delete_virtual_tour(self, tour_id: str) -> DeleteVirtualTourResponse:
        """Delete a tour. Its public link then returns 404; its 360° photos stay
        in the property. (``/delete_virtual_tour``)"""
        data = self._post("/delete_virtual_tour", tour_id=tour_id)
        return DeleteVirtualTourResponse(
            message=data.get("message"),
            tour_id=data.get("tourId", tour_id),
            raw=data,
        )

    def create_upload_link(
        self,
        *,
        property_id: Optional[str] = None,
        name: Optional[str] = None,
        type: Optional[str] = None,
        language: Optional[str] = None,
    ) -> UploadLinkResponse:
        """Get a no-login upload page (phone or computer, valid 24 h, up to
        100 files) where someone drops photos into a property.

        ``type="any"`` (the default) takes regular photos and 360° photos (2:1
        images are stored as 360° photos automatically); ``type="360"`` takes
        only 360° photos — use it for a virtual tour. When they're done, list
        them with ``list_property_images(property_id)`` (``type="360"`` for
        360° photos) or call ``create_virtual_tour(property_id=...)``. Creates
        the property if no ``property_id`` is given. Over the daily link limit
        (5 free, 50 paid) this raises :class:`PedraAPIError` with status 429
        and ``code == "upload_link_limit"``. (``/create_upload_link``)"""
        data = self._post(
            "/create_upload_link",
            property_id=property_id,
            name=name,
            type=type,
            language=language,
        )
        max_files = data.get("maxFiles")
        return UploadLinkResponse(
            message=data.get("message"),
            upload_url=data.get("uploadUrl", ""),
            property_id=data.get("propertyId", property_id or ""),
            property_name=data.get("propertyName"),
            type=data.get("type", type),
            expires_at=data.get("expiresAt"),
            max_files=int(max_files) if max_files is not None else None,
            app_url=data.get("appUrl"),
            raw=data,
        )

    def wait_for_virtual_tour(
        self, tour_id: str, *, interval: float = 5.0, timeout: float = 900.0
    ) -> VirtualTour:
        """Poll :meth:`get_virtual_tour` until the tour is ``"ready"`` or
        ``"failed"`` and return it (a failed tour is returned, not raised —
        check ``status`` and ``error``). Raises :class:`PedraError` if it is
        still processing after ``timeout`` seconds.

        Example::

            tour = pedra.create_virtual_tour(image_urls=[...])
            tour = pedra.wait_for_virtual_tour(tour.tour_id)
            if tour.status == "ready":
                print(tour.tour_url)
        """
        deadline = time.monotonic() + timeout
        while True:
            tour = self.get_virtual_tour(tour_id)
            if tour.status in ("ready", "failed"):
                return tour
            if time.monotonic() + interval > deadline:
                raise PedraError(
                    f"Virtual tour {tour_id} was still {tour.status} after {timeout}s"
                )
            time.sleep(interval)

    def credits(self) -> CreditsResponse:
        """Read the account's remaining credits and plan. Never deducts credits."""
        data = self._post("/credits")
        return CreditsResponse(
            plan=data.get("plan", "free"),
            credits_remaining=int(data.get("creditsRemaining", 0) or 0),
            raw=data,
        )

    def feedback(
        self,
        *,
        image_url: Optional[str] = None,
        image_id: Optional[str] = None,
        vote: Optional[str] = None,
        comment: Optional[str] = None,
        credit_back: Optional[bool] = None,
    ) -> FeedbackResponse:
        """Submit thumbs up/down feedback on a generated image, with an optional
        credit-back on a thumbs-down (subject to the API's eligibility rules).
        Provide one of ``image_url`` or ``image_id``."""
        data = self._post(
            "/feedback",
            image_url=image_url,
            image_id=image_id,
            vote=vote,
            comment=comment,
            credit_back=credit_back,
        )
        return FeedbackResponse(
            message=data.get("message"),
            credited_back=data.get("creditedBack", data.get("creditBack")),
            raw=data,
        )

    # --- internals -----------------------------------------------------------

    def _post(
        self,
        path: str,
        *,
        _raw: Optional[Dict[str, Any]] = None,
        _tour: bool = False,
        **params: Any,
    ) -> Dict[str, Any]:
        # Drop unset optionals, then convert keys to the camelCase wire format.
        # ``_raw`` holds fields sent as-is (their keys are data, e.g. scene ids).
        # ``_tour``: the response is a tour, whose ``error`` field is why a build
        # failed (HTTP 200, status "failed") — data, not a failed request.
        body = _camelize({k: v for k, v in params.items() if v is not None})
        if _raw:
            body.update(_raw)
        body["apiKey"] = self.api_key
        return _http_post(
            self.base_url, path, body, timeout=self.timeout,
            ssl_context=self._ssl_context, tour=_tour,
        )

    _parse = staticmethod(_parse_json)

    @staticmethod
    def _tour(data: Dict[str, Any]) -> VirtualTour:
        return VirtualTour(
            tour_id=data.get("tourId", ""),
            property_id=data.get("propertyId"),
            name=data.get("name"),
            status=data.get("status", ""),
            tour_url=data.get("tourUrl", ""),
            embed_code=data.get("embedCode", ""),
            app_url=data.get("appUrl"),
            shareable=data.get("shareable"),
            shareable_note=data.get("shareableNote"),
            scene_count=data.get("sceneCount"),
            link_count=data.get("linkCount"),
            cover_image_url=data.get("coverImageUrl"),
            created_at=data.get("createdAt"),
            updated_at=data.get("updatedAt"),
            progress=data.get("progress"),
            error=data.get("error"),
            last_error=data.get("lastError"),
            failed_scenes=data.get("failedScenes"),
            scenes=data.get("scenes"),
            links=data.get("links"),
            settings=data.get("settings"),
            message=data.get("message"),
            linking=data.get("linking"),
            credits_cost=data.get("creditsCost"),
            estimated_seconds=data.get("estimatedSeconds"),
            added_scenes=data.get("addedScenes"),
            raw=data,
        )

    @staticmethod
    def _image(data: Dict[str, Any]) -> ImageResponse:
        output = data.get("output")
        urls: List[str] = []
        if isinstance(output, list):
            urls = [o["url"] for o in output if isinstance(o, dict) and o.get("url")]
        elif isinstance(output, dict) and output.get("url"):
            urls = [output["url"]]
        return ImageResponse(message=data.get("message"), urls=urls, raw=data)
