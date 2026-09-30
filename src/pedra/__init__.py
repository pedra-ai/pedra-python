"""Official Python SDK for the Pedra API.

>>> from pedra import Pedra
>>> pedra = Pedra("YOUR_API_KEY")
>>> result = pedra.furnish(image_url="https://example.com/room.jpg", style="Minimalist")
>>> print(result.url)
"""

from .client import Pedra
from .access import get_access_status, request_access, wait_for_access
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
    TourLinkInput,
    TourSceneInput,
    UploadLinkResponse,
    VideoResponse,
    VirtualTour,
    VirtualToursResponse,
    VoiceResponse,
)

__version__ = "0.4.0"

__all__ = [
    "Pedra",
    "request_access",
    "get_access_status",
    "wait_for_access",
    "AccessRequest",
    "AccessStatus",
    "PedraError",
    "PedraAPIError",
    "ImageResponse",
    "VideoResponse",
    "CreditsResponse",
    "FeedbackResponse",
    "ScriptResponse",
    "VoiceResponse",
    "MusicLibraryResponse",
    "PropertiesResponse",
    "PropertyImagesResponse",
    "PropertyResponse",
    "AddImagesResponse",
    "VirtualTour",
    "VirtualToursResponse",
    "DeleteVirtualTourResponse",
    "UploadLinkResponse",
    "TourSceneInput",
    "TourLinkInput",
    "__version__",
]
