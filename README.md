# Pedra Python SDK

Official Python SDK for the [Pedra API](https://pedra.ai/api-documentation) — AI photo editing for real estate: virtual staging, renovation, room emptying, image enhancement, sky replacement, object removal/blur, property videos, and hosted 360° virtual tours.

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

Get your API key from your [Pedra account settings](https://app.pedra.ai). Every photo and video method blocks until the asset is ready and returns the final URL(s) — there are no job IDs to poll. The API uses a heartbeat to keep long requests (like `create_video`) alive. [Virtual tours](#virtual-tours) are the exception: they build in the background and you poll for them.

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

### No Pedra account yet?

An agent or script can get a key for a person without a browser in the loop.
Pedra emails them a confirmation link (valid 30 min): a new account chooses a
password there, an existing one just clicks "Allow". Nothing is created until
they click, and they can decline. No API key is needed for these calls:

```python
from pedra import Pedra, request_access, wait_for_access

req = request_access("ana@agency.com", agent_name="My listing script")
print("Check your email and confirm to give this script access to Pedra.")

res = wait_for_access(req.request_id)  # polls every 5 s, up to 30 min
if res.approved:
    # Store res.api_key somewhere safe (it can be fetched for 15 min after approval).
    pedra = Pedra(res.api_key)
    if res.note:
        print(res.note)  # e.g. a new free account unlocks its trial at app.pedra.ai
else:
    print("Access", res.status)  # "denied" or "expired"
```

`Pedra.request_access` / `Pedra.get_access_status` / `Pedra.wait_for_access`
are the same functions. The response is the same whether or not the address
already has an account. Inbox confirmation is required, disposable email
domains are refused (400, `code == "disposable_email"`), and requests are
rate-limited (429, `code == "rate_limited"`).

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
| `furnish(image_url, *, room_type=None, style=None)` | `/furnish` | `ImageResponse` |
| `renovation(image_url, *, style=None, furnish=None, room_type=None)` | `/renovation` | `ImageResponse` |
| `edit_via_prompt(image_url, prompt)` | `/edit_via_prompt` | `ImageResponse` |
| `sky(image_url, *, sky_style=None)` | `/sky_blue` | `ImageResponse` |
| `remove(image_url, mask_url)` | `/remove_object` | `ImageResponse` |
| `blur(image_url, objects_to_blur)` | `/blur` | `ImageResponse` |
| `create_video(images, *, music=None, voice=None, branding=None, ending_title=None, ending_subtitle=None, is_vertical=None, property_characteristics=None)` | `/create_video` | `VideoResponse` |
| `update_video(video_id, *, images=None, music=None, voice=None, branding=None, ending_title=None, ending_subtitle=None, is_vertical=None, property_characteristics=None)` | `/update_video` | `VideoResponse` |
| `generate_voice_script(*, images=None, property_characteristics=None, language=None)` | `/generate_voice_script` | `ScriptResponse` |
| `generate_voice(text, *, language=None, voice_id=None)` | `/generate_voice` | `VoiceResponse` |
| `music_library()` | `/music_library` | `MusicLibraryResponse` (tracks, voice languages, voices) |
| `list_properties()` | `/list_properties` | `PropertiesResponse` |
| `list_property_images(property_id, *, type=None)` | `/list_property_images` | `PropertyImagesResponse` |
| `create_property(*, name=None)` | `/create_property` | `PropertyResponse` |
| `add_images_to_property(property_id, image_urls, *, type=None)` | `/add_images_to_property` | `AddImagesResponse` |
| `add_local_panoramas(property_id, paths, *, max_request_bytes=...)` | `/add_images_to_property` (batched) | `AddImagesResponse` |
| `create_virtual_tour(scenes=None, *, image_urls=None, property_id=None, name=None, linking=None, language=None)` | `/create_virtual_tour` | `VirtualTour` |
| `get_virtual_tour(tour_id)` | `/get_virtual_tour` | `VirtualTour` |
| `wait_for_virtual_tour(tour_id, *, interval=5.0, timeout=900.0)` | polls `/get_virtual_tour` | `VirtualTour` |
| `list_virtual_tours(*, property_id=None)` | `/list_virtual_tours` | `VirtualToursResponse` |
| `update_virtual_tour(tour_id, *, name=None, scene_names=None, scene_order=None, remove_scenes=None, links=None, navigation_style=None, navigation_size=None, show_labels=None, language=None)` | `/update_virtual_tour` | `VirtualTour` |
| `add_virtual_tour_scenes(tour_id, scenes, *, linking=None)` | `/add_virtual_tour_scenes` | `VirtualTour` |
| `delete_virtual_tour(tour_id)` | `/delete_virtual_tour` | `DeleteVirtualTourResponse` |
| `create_upload_link(*, property_id=None, name=None, type=None, language=None)` | `/create_upload_link` | `UploadLinkResponse` |
| `credits()` | `/credits` | `CreditsResponse` |
| `feedback(*, image_url=None, image_id=None, vote=None, comment=None, credit_back=None)` | `/feedback` | `FeedbackResponse` |

### Examples

```python
# Enhance — preserve exact framing (verification verticals)
pedra.enhance(image_url=url, preserve_original_framing=True)

# Empty a room
result = pedra.empty(url)

# Renovate, furnished
pedra.renovation(url, style="Scandinavian", furnish=True)

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

## Virtual tours

POST your 360° photos, get back a hosted, linked, shareable virtual tour. AI
names the rooms and places the door-to-door navigation points. Photos must be
2:1 equirectangular (JPEG/PNG/WebP, up to 80 MB each; max 50 rooms per tour).

Unlike the other methods, building a tour is **asynchronous**:
`create_virtual_tour` returns straight away with `status == "processing"`
(about 10 s per linked room), and `wait_for_virtual_tour` polls until it's
`"ready"` or `"failed"`.

```python
tour = pedra.create_virtual_tour(
    [  # in walking order; omit "name" and AI names the room
        {"image_url": "https://example.com/360/entrance.jpg", "name": "Entrance"},
        {"image_url": "https://example.com/360/living-room.jpg"},
        {"image_url": "https://example.com/360/kitchen.jpg"},
    ],
    name="Calle Mayor 12",
)

tour = pedra.wait_for_virtual_tour(tour.tour_id)
if tour.status == "ready":
    print(tour.tour_url)    # share this
    print(tour.embed_code)  # or embed this <iframe>
else:
    print(tour.error, tour.failed_scenes)  # failed builds cost nothing
```

**Linking** (`linking=`): `"sequential"` (default) links each room to the next,
both ways — pass rooms in walking order; costs `max(3, ceil(rooms / 3))`
credits. `"smart"` lets AI work out which rooms visibly connect (slower, up to
40 rooms, 5–160 credits by room count). `"none"` is free — place links yourself
with `update_virtual_tour(links=...)`. Credits are only charged when linking
starts. `language` (`en` `es` `fr` `de` `it` `pt`) sets the tour page's language
and the AI room names. One tour per property; a second `create_virtual_tour` on
the same property raises `PedraAPIError` with status 409
(`err.body["code"] == "tour_exists"`, `err.body["tourId"]`).

Nested tour data (`scenes`, `links`, `settings`, `progress`) comes back as the
API's dicts, with camelCase keys (`scene["sceneId"]`, `link["fromSceneId"]`).

**360° photos on disk** — `add_local_panoramas` base64-encodes local files and
adds them to a property in order (batched under the API's 10-per-call and
50 MB limits); then build the tour from every 360° photo in the property:

```python
prop = pedra.create_property(name="Calle Mayor 12")
res = pedra.add_local_panoramas(
    prop.property_id,
    ["360/01-entrance.jpg", "360/02-living.jpg", "360/03-kitchen.jpg"],
)
print(len(res.added), res.failed)  # each entry carries its "path"
tour = pedra.create_virtual_tour(property_id=prop.property_id)
```

Files over ~33 MB are too big to send inline; `create_upload_link` gives you a
no-login page (phone or computer, valid 24 h, up to 100 files) where anyone can
drop photos into a property — then call `create_virtual_tour(property_id=...)`:

```python
link = pedra.create_upload_link(name="Calle Mayor 12", type="360")
print(link.upload_url, link.property_id)
```

`type="360"` takes only 360° photos. The default, `"any"`, takes regular photos
too (2:1 images are stored as 360° photos automatically; iPhone HEIC works from
Safari), so the same link works for photos to edit or turn into a video: list
them afterwards with `list_property_images(property_id)`.

**Editing** is free and instant:

```python
pedra.update_virtual_tour(
    tour.tour_id,
    scene_names={scene_id: "Kitchen"},
    scene_order=[entrance_id, living_id, kitchen_id],  # first one opens the tour
    navigation_style="blue",   # "white" | "blue"
    navigation_size="large",   # "small" | "medium" | "large"
    show_labels=True,
)

# Append rooms (links only the new stretch), then wait again.
pedra.add_virtual_tour_scenes(tour.tour_id, [{"image_url": "https://example.com/360/terrace.jpg"}])
pedra.wait_for_virtual_tour(tour.tour_id)

# List the 360° photos in a property (their imageIds are scene ids).
photos = pedra.list_property_images(prop.property_id, type="360")
```

On the free plan the tour builds, but its public link shows an upgrade page:
responses carry `shareable=False` and a `shareable_note`.

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

`err.code` carries the API's machine-readable code when there is one. Limits
worth handling:

| Status | `code` | When |
|---|---|---|
| 429 | `upload_limit` | Daily upload limit reached (30 images/day free, 500 paid, reset at midnight UTC). Counts every image stored from outside the app: `add_images_to_property`, URL scenes in `create_virtual_tour` / `add_virtual_tour_scenes`, and upload-link files. The whole call is refused; nothing is stored. |
| 429 | `upload_link_limit` | Too many upload links today (5 free, 50 paid). Reuse one of today's links. |
| 429 | `rate_limited` | Too many `request_access` calls. |
| 409 | `tour_exists` | The property already has a virtual tour. |

`PedraAPIError` is also raised when a long request fails *after* the heartbeat
has started — the API returns HTTP 200 with an `{"error": ...}` body in that
case, and the SDK surfaces it as an error anyway.

## Links

- API documentation: https://pedra.ai/api-documentation
- Pedra: https://pedra.ai

## License

MIT
