"""Official Python SDK for the Pedra API.

>>> from pedra import Pedra
>>> pedra = Pedra("YOUR_API_KEY")
>>> result = pedra.furnish(image_url="https://example.com/room.jpg", style="Minimalist")
>>> print(result.url)
"""

from .client import Pedra
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

__version__ = "0.3.0"

__all__ = [
    "Pedra",
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
    "__version__",
]
