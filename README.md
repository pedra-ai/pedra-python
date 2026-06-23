# Pedra Python SDK

Official Python SDK for the [Pedra API](https://pedra.ai/api-documentation) — AI photo editing for real estate: virtual staging, renovation, room emptying, image enhancement, sky replacement, object removal/blur, and property videos.

[![PyPI version](https://img.shields.io/pypi/v/pedra.svg)](https://pypi.org/project/pedra/)

```bash
pip install pedra
```

Requires Python 3.8+. Zero runtime dependencies (uses the standard library).

## Quick start

```python
from pedra import Pedra

pedra = Pedra("YOUR_API_KEY")  # or set PEDRA_API_KEY in the environment

result = pedra.furnish(
    image_url="https://example.com/empty-living-room.jpg",
    room_type="Living room",
    style="Minimalist",
)

print(result.url)   # → the staged image URL
print(result.urls)  # → all generated URLs
```

Get your API key from your [Pedra account settings](https://app.pedra.ai). Every method blocks until the asset is ready and returns the final URL(s) — there are no job IDs to poll. The API uses a heartbeat to keep long requests (like `create_video`) alive.

## Authentication

```python
pedra = Pedra("YOUR_API_KEY")
# or
pedra = Pedra()  # reads PEDRA_API_KEY from the environment
```

Options:

```python
pedra = Pedra(
    "YOUR_API_KEY",
    base_url="https://app.pedra.ai/api",  # default
    timeout=600.0,                        # seconds, default 10 min (covers create_video)
)
```

## Responses

Image methods return an `ImageResponse`, which normalizes the underlying
endpoint's output (some return a list, some a single object):

```python
@dataclass
class ImageResponse:
    message: Optional[str]
    urls: List[str]   # every generated asset URL
    raw: Any          # the untouched API response
    # .url -> Optional[str]: convenience for the first URL
```

## Methods

| Method | Endpoint | Returns |
| --- | --- | --- |
| `enhance(image_url, *, preserve_original_framing=None)` | `/enhance` | `ImageResponse` |
| `enhance_and_correct_perspective(image_url, *, preserve_original_framing=None)` | `/enhance_and_correct_perspective` | `ImageResponse` |
| `empty(image_url)` | `/empty_room` | `ImageResponse` |
| `furnish(image_url, *, room_type=None, style=None, creativity=None)` | `/furnish` | `ImageResponse` |
| `renovation(image_url, *, style=None, creativity=None, furnish=None, room_type=None)` | `/renovation` | `ImageResponse` |
| `edit_via_prompt(image_url, prompt)` | `/edit_via_prompt` | `ImageResponse` |
| `sky(image_url, *, sky_style=None)` | `/sky_blue` | `ImageResponse` |
| `remove(image_url, mask_url)` | `/remove_object` | `ImageResponse` |
| `blur(image_url, objects_to_blur)` | `/blur` | `ImageResponse` |
| `create_video(images, *, music=None, voice=None, branding=None, ending_title=None, ending_subtitle=None, is_vertical=None, property_characteristics=None)` | `/create_video` | `VideoResponse` |
| `credits()` | `/credits` | `CreditsResponse` |
| `feedback(*, image_url=None, image_id=None, vote=None, comment=None, credit_back=None)` | `/feedback` | `FeedbackResponse` |

### Examples

```python
# Enhance — preserve exact framing (verification verticals)
pedra.enhance(image_url=url, preserve_original_framing=True)

# Empty a room
result = pedra.empty(url)

# Renovate, furnished, high creativity
pedra.renovation(url, style="Scandinavian", creativity="High", furnish=True)

# Edit via prompt
pedra.edit_via_prompt(url, "Add a large green plant in the corner")

# Sky replacement
pedra.sky(url)

# Remove an object using a mask
pedra.remove(url, mask_url)

# Blur faces / plates
pedra.blur(url, ["faces", "license_plates"])

# Credits
info = pedra.credits()
print(info.plan, info.credits_remaining)

# Feedback + credit-back on a bad result
pedra.feedback(image_url=url, vote="down", comment="Artifacts on the wall", credit_back=True)
```

### Creating a video

`create_video` blocks server-side (up to ~10 minutes) while the video renders,
then returns the finished URL inline. Image dicts use snake_case keys — the SDK
converts them to the API's wire format for you:

```python
video = pedra.create_video(
    images=[
        {"image_url": "https://example.com/photo1.jpg", "effect": "zoom-in", "title": "Living room"},
        {"image_url": "https://example.com/photo2.jpg", "effect": "zoom-out"},
        {
            "image_url": "https://example.com/before.jpg",
            "effect": "transition",
            "second_image_url": "https://example.com/after.jpg",
        },
    ],
    music={"enabled": True, "track": "calm"},
    branding={"show_watermark": True},
    ending_title="Contact us",
    ending_subtitle="+1 555 0100",
    is_vertical=False,
    property_characteristics=[
        {"label": "Bedrooms", "value": "3"},
        {"label": "Bathrooms", "value": "2"},
    ],
)

print(video.video_url)
```

Per-image `effect` is one of `zoom-in` (default), `zoom-out`, `transition`
(requires `second_image_url`), or `static`. Each non-static image costs 5 credits.

## Error handling

```python
from pedra import PedraAPIError, PedraError

try:
    pedra.enhance(url)
except PedraAPIError as err:
    print(err.status, err, err.body)
except PedraError as err:
    print("Client/network error:", err)
```

`PedraAPIError` is also raised when a long request fails *after* the heartbeat
has started — the API returns HTTP 200 with an `{"error": ...}` body in that
case, and the SDK surfaces it as an error anyway.

## Links

- API documentation: https://pedra.ai/api-documentation
- Pedra: https://pedra.ai

## License

MIT
