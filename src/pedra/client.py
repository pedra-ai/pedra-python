"""Synchronous client for the Pedra API."""

import json
import os
import ssl
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional

from .errors import PedraAPIError, PedraError
from .models import (
    AddImagesResponse,
    CreditsResponse,
    FeedbackResponse,
    ImageResponse,
    MusicLibraryResponse,
    PropertyImagesResponse,
    PropertyResponse,
    PropertiesResponse,
    ScriptResponse,
    VideoResponse,
    VoiceResponse,
)

DEFAULT_BASE_URL = "https://app.pedra.ai/api"
# createVideo blocks server-side until the video is rendered (up to ~10 min).
DEFAULT_TIMEOUT = 600.0


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
                "set the PEDRA_API_KEY environment variable."
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
        """Virtually stage / furnish a room."""
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
        ("With furniture" / "Empty" / "Auto")."""
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
        self, text: str, *, language: Optional[str] = None
    ) -> VoiceResponse:
        """Render a voiceover from a script via TTS.

        Returns an ``audio_id`` to pass as a video's ``voice={"audio_id": ...}``
        (which also drives synced subtitles). (``/generate_voice``)
        """
        data = self._post("/generate_voice", text=text, language=language)
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
            raw=data,
        )

    def list_properties(self) -> PropertiesResponse:
        """List the account's properties (id, name, photo count, appUrl). Use it to
        find photos already in the account. (``/list_properties``)"""
        data = self._post("/list_properties")
        return PropertiesResponse(properties=data.get("properties", []), raw=data)

    def list_property_images(self, property_id: str) -> PropertyImagesResponse:
        """List a property's photos as public URLs, ready to pass to
        :meth:`create_video` or the edit methods. (``/list_property_images``)"""
        data = self._post("/list_property_images", property_id=property_id)
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
        self, property_id: str, image_urls: List[str]
    ) -> AddImagesResponse:
        """Add photos to a property by URL — the server fetches and stores each one,
        so any public https image URL works. (``/add_images_to_property``)"""
        data = self._post(
            "/add_images_to_property", property_id=property_id, image_urls=image_urls
        )
        return AddImagesResponse(
            message=data.get("message"),
            property_id=data.get("propertyId", property_id),
            added=data.get("added", []),
            failed=data.get("failed", []),
            app_url=data.get("appUrl"),
            raw=data,
        )

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

    def _post(self, path: str, **params: Any) -> Dict[str, Any]:
        # Drop unset optionals, then convert keys to the camelCase wire format.
        body = _camelize({k: v for k, v in params.items() if v is not None})
        body["apiKey"] = self.api_key
        payload = json.dumps(body).encode("utf-8")

        request = urllib.request.Request(
            f"{self.base_url}{path}",
            data=payload,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
        )

        try:
            with urllib.request.urlopen(
                request, timeout=self.timeout, context=self._ssl_context
            ) as response:
                status = response.getcode()
                text = response.read().decode("utf-8")
        except urllib.error.HTTPError as err:  # non-2xx
            text = err.read().decode("utf-8", errors="replace")
            data = self._parse(text)
            message = (
                (data.get("error") or data.get("message"))
                if isinstance(data, dict)
                else None
            ) or f"Request to {path} failed with status {err.code}"
            raise PedraAPIError(message, status=err.code, body=data) from None
        except urllib.error.URLError as err:
            raise PedraError(f"Network error calling {path}: {err.reason}") from err
        except TimeoutError as err:
            raise PedraError(
                f"Request to {path} timed out after {self.timeout}s"
            ) from err

        data = self._parse(text)
        if data is None:
            raise PedraError(f"Could not parse the response from {path}")

        # Heartbeat caveat: a request that runs long and then fails returns HTTP
        # 200 with an ``{"error": ...}`` body (the 200 header was already sent).
        if isinstance(data, dict) and data.get("error"):
            raise PedraAPIError(str(data["error"]), status=status, body=data)

        return data

    @staticmethod
    def _parse(text: str) -> Any:
        # json.loads tolerates the leading whitespace the heartbeat prepends.
        if not text or not text.strip():
            return None
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return None

    @staticmethod
    def _image(data: Dict[str, Any]) -> ImageResponse:
        output = data.get("output")
        urls: List[str] = []
        if isinstance(output, list):
            urls = [o["url"] for o in output if isinstance(o, dict) and o.get("url")]
        elif isinstance(output, dict) and output.get("url"):
            urls = [output["url"]]
        return ImageResponse(message=data.get("message"), urls=urls, raw=data)
