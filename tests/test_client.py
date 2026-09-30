"""Tests for the Pedra Python client.

Run with: python -m unittest discover -s tests
"""

import io
import json
import os
import shutil
import tempfile
import unittest
import urllib.error
from unittest import mock

from pedra import Pedra, PedraAPIError, PedraError, get_access_status, request_access, wait_for_access
from pedra.client import _camelize


class FakeResponse:
    def __init__(self, text, status=200):
        self._text = text
        self._status = status

    def read(self):
        return self._text.encode("utf-8")

    def getcode(self):
        return self._status

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def patch_urlopen(text, status=200):
    captured = {}

    def fake_urlopen(request, timeout=None, context=None):
        captured["url"] = request.full_url
        captured["body"] = json.loads(request.data.decode("utf-8"))
        captured["timeout"] = timeout
        captured["context"] = context
        return FakeResponse(text, status)

    return mock.patch("urllib.request.urlopen", fake_urlopen), captured


class ClientTests(unittest.TestCase):
    def test_requires_api_key(self):
        with mock.patch.dict("os.environ", {}, clear=True):
            with self.assertRaises(PedraError):
                Pedra()

    def test_sends_apikey_and_camelcased_params(self):
        patcher, captured = patch_urlopen(
            json.dumps({"message": "ok", "output": [{"url": "https://x/1"}]})
        )
        with patcher:
            pedra = Pedra("k")
            res = pedra.furnish(image_url="https://img", room_type="Living room")

        self.assertEqual(captured["url"], "https://app.pedra.ai/api/furnish")
        self.assertEqual(
            captured["body"],
            {"apiKey": "k", "imageUrl": "https://img", "roomType": "Living room"},
        )
        self.assertEqual(res.url, "https://x/1")
        self.assertEqual(res.urls, ["https://x/1"])

    def test_drops_unset_optionals(self):
        patcher, captured = patch_urlopen(json.dumps({"output": {"url": "u"}}))
        with patcher:
            Pedra("k").enhance(image_url="https://img")
        self.assertNotIn("preserveOriginalFraming", captured["body"])

    def test_normalizes_single_object_output(self):
        patcher, _ = patch_urlopen(json.dumps({"output": {"url": "https://x/2"}}))
        with patcher:
            res = Pedra("k").edit_via_prompt(image_url="https://img", prompt="cozy")
        self.assertEqual(res.url, "https://x/2")
        self.assertEqual(res.urls, ["https://x/2"])

    def test_tolerates_heartbeat_whitespace(self):
        patcher, _ = patch_urlopen("    " + json.dumps({"output": [{"url": "https://x/3"}]}))
        with patcher:
            res = Pedra("k").enhance(image_url="https://img")
        self.assertEqual(res.url, "https://x/3")

    def test_raises_on_200_with_error_body(self):
        patcher, _ = patch_urlopen(json.dumps({"error": "Video processing failed"}))
        with patcher:
            with self.assertRaises(PedraAPIError):
                Pedra("k").create_video(images=[{"image_url": "https://img"}])

    def test_credits(self):
        patcher, _ = patch_urlopen(json.dumps({"plan": "pro", "creditsRemaining": 42}))
        with patcher:
            res = Pedra("k").credits()
        self.assertEqual(res.plan, "pro")
        self.assertEqual(res.credits_remaining, 42)

    def test_create_video_deep_camelizes(self):
        patcher, captured = patch_urlopen(
            json.dumps({"videoId": "v1", "videoUrl": "https://v/1"})
        )
        with patcher:
            res = Pedra("k").create_video(
                images=[{"image_url": "https://a", "second_image_url": "https://b"}],
                voice={"enabled": True, "audio_url": "https://aud"},
                is_vertical=True,
            )
        self.assertEqual(captured["body"]["images"][0]["imageUrl"], "https://a")
        self.assertEqual(captured["body"]["images"][0]["secondImageUrl"], "https://b")
        self.assertEqual(captured["body"]["voice"]["audioUrl"], "https://aud")
        self.assertTrue(captured["body"]["isVertical"])
        self.assertEqual(res.video_url, "https://v/1")

    def test_update_video_camelizes_and_targets_endpoint(self):
        patcher, captured = patch_urlopen(
            json.dumps({"videoId": "v1", "videoUrl": "https://v/2"})
        )
        with patcher:
            res = Pedra("k").update_video(
                "v1",
                music={"track": "cinematic"},
                voice={"audio_id": "a1", "show_subtitles": False},
            )
        self.assertEqual(captured["url"], "https://app.pedra.ai/api/update_video")
        self.assertEqual(captured["body"]["videoId"], "v1")
        self.assertEqual(captured["body"]["voice"]["audioId"], "a1")
        self.assertFalse(captured["body"]["voice"]["showSubtitles"])
        # images omitted → patch-style metadata edit
        self.assertNotIn("images", captured["body"])
        self.assertEqual(res.video_url, "https://v/2")

    def test_generate_voice(self):
        patcher, captured = patch_urlopen(
            json.dumps(
                {"audioId": "a1", "audioUrl": "https://aud/1", "duration": 7}
            )
        )
        with patcher:
            res = Pedra("k").generate_voice("A bright home.", language="Español")
        self.assertEqual(captured["url"], "https://app.pedra.ai/api/generate_voice")
        self.assertEqual(captured["body"]["text"], "A bright home.")
        self.assertEqual(captured["body"]["language"], "Español")
        self.assertEqual(res.audio_id, "a1")
        self.assertEqual(res.duration, 7)

    def test_generate_voice_with_voice_id(self):
        patcher, captured = patch_urlopen(json.dumps({"audioId": "a1"}))
        with patcher:
            Pedra("k").generate_voice(
                "A bright home.", voice_id="JBFqnCBsd6RMkjVDRZzb"
            )
        self.assertEqual(captured["body"]["voiceId"], "JBFqnCBsd6RMkjVDRZzb")

    def test_generate_voice_omits_unset_voice_id(self):
        patcher, captured = patch_urlopen(json.dumps({"audioId": "a1"}))
        with patcher:
            Pedra("k").generate_voice("A bright home.")
        self.assertNotIn("voiceId", captured["body"])

    def test_generate_voice_script(self):
        patcher, captured = patch_urlopen(json.dumps({"script": "Lovely place."}))
        with patcher:
            res = Pedra("k").generate_voice_script(
                images=["https://a"],
                property_characteristics=[{"label": "Bedrooms", "value": "3"}],
            )
        self.assertEqual(
            captured["url"], "https://app.pedra.ai/api/generate_voice_script"
        )
        self.assertEqual(captured["body"]["images"], ["https://a"])
        self.assertEqual(
            captured["body"]["propertyCharacteristics"][0]["label"], "Bedrooms"
        )
        self.assertEqual(res.script, "Lovely place.")

    def test_music_library(self):
        patcher, _ = patch_urlopen(
            json.dumps(
                {
                    "tracks": [{"track": "chill", "label": "Chill Beats"}],
                    "variantsPerTrack": 6,
                    "defaultTrack": "chill",
                    "voiceLanguages": ["English"],
                    "voicesByLanguage": [
                        {
                            "language": "English",
                            "voices": [{"voiceId": "v1", "name": "Rachel"}],
                        }
                    ],
                }
            )
        )
        with patcher:
            res = Pedra("k").music_library()
        self.assertEqual(res.voices_by_language[0]["voices"][0]["name"], "Rachel")
        self.assertEqual(res.default_track, "chill")
        self.assertEqual(res.variants_per_track, 6)
        self.assertEqual(res.tracks[0]["track"], "chill")

    def test_list_properties(self):
        patcher, captured = patch_urlopen(
            json.dumps({"properties": [{"propertyId": "p1", "name": "Listing", "photoCount": 3}]})
        )
        with patcher:
            res = Pedra("k").list_properties()
        self.assertEqual(captured["url"], "https://app.pedra.ai/api/list_properties")
        self.assertEqual(res.properties[0]["propertyId"], "p1")

    def test_list_property_images(self):
        patcher, captured = patch_urlopen(
            json.dumps({"propertyId": "p1", "images": [{"imageId": "i1", "url": "https://img.pedra.ai/i1"}]})
        )
        with patcher:
            res = Pedra("k").list_property_images("p1")
        self.assertEqual(captured["body"]["propertyId"], "p1")
        self.assertEqual(res.images[0]["url"], "https://img.pedra.ai/i1")

    def test_create_property(self):
        patcher, captured = patch_urlopen(
            json.dumps({"message": "Property created", "propertyId": "p2", "appUrl": "https://app.pedra.ai/?propertyId=p2"})
        )
        with patcher:
            res = Pedra("k").create_property(name="New listing")
        self.assertEqual(captured["url"], "https://app.pedra.ai/api/create_property")
        self.assertEqual(captured["body"]["name"], "New listing")
        self.assertEqual(res.property_id, "p2")
        self.assertIn("propertyId=p2", res.app_url)

    def test_add_images_to_property_camelizes(self):
        patcher, captured = patch_urlopen(
            json.dumps({"message": "Added 1 image(s)", "propertyId": "p1", "added": [{"imageId": "i9", "url": "https://img.pedra.ai/i9"}], "failed": []})
        )
        with patcher:
            res = Pedra("k").add_images_to_property("p1", ["https://x/a.jpg"])
        self.assertEqual(captured["url"], "https://app.pedra.ai/api/add_images_to_property")
        self.assertEqual(captured["body"]["propertyId"], "p1")
        self.assertEqual(captured["body"]["imageUrls"], ["https://x/a.jpg"])
        self.assertEqual(res.added[0]["url"], "https://img.pedra.ai/i9")


TOUR = {
    "tourId": "t1",
    "propertyId": "p1",
    "name": "Calle Mayor 12",
    "status": "ready",
    "tourUrl": "https://app.pedra.ai/virtual-tour/t1",
    "embedCode": "<iframe></iframe>",
    "appUrl": "https://app.pedra.ai/?projectId=p1",
    "shareable": True,
    "sceneCount": 2,
    "linkCount": 2,
    "coverImageUrl": "https://img.pedra.ai/s1",
    "scenes": [{"sceneId": "s1", "name": "Entrance", "imageUrl": "https://img.pedra.ai/s1"}],
    "links": [{"linkId": "ai-1", "fromSceneId": "s1", "toSceneId": "s2", "yaw": -18, "pitch": 0}],
    "settings": {"navigationStyle": "white", "navigationSize": "medium", "showLabels": False, "language": "en"},
}


def patch_urlopen_sequence(responses):
    """Return a different canned body per call; records every request body."""
    calls = []

    def fake_urlopen(request, timeout=None, context=None):
        calls.append(
            {"url": request.full_url, "body": json.loads(request.data.decode("utf-8"))}
        )
        return FakeResponse(responses[min(len(calls) - 1, len(responses) - 1)])

    return mock.patch("urllib.request.urlopen", fake_urlopen), calls


def patch_urlopen_panoramas():
    """Fake add_images_to_property: every data URI sent is 'added'."""
    calls = []
    counter = {"n": 0}

    def fake_urlopen(request, timeout=None, context=None):
        body = json.loads(request.data.decode("utf-8"))
        calls.append({"url": request.full_url, "body": body})
        added = []
        for _ in body["imageUrls"]:
            counter["n"] += 1
            n = counter["n"]
            added.append({"imageId": f"s{n}", "url": f"https://img.pedra.ai/s{n}", "aspectRatio": 2})
        return FakeResponse(
            json.dumps({"propertyId": body["propertyId"], "type": "360", "added": added, "failed": []})
        )

    return mock.patch("urllib.request.urlopen", fake_urlopen), calls


class VirtualTourTests(unittest.TestCase):
    def test_list_property_images_type_360(self):
        patcher, captured = patch_urlopen(json.dumps({"propertyId": "p1", "images": []}))
        with patcher:
            Pedra("k").list_property_images("p1", type="360")
        self.assertEqual(captured["body"]["type"], "360")

    def test_list_property_images_omits_unset_type(self):
        patcher, captured = patch_urlopen(json.dumps({"propertyId": "p1", "images": []}))
        with patcher:
            Pedra("k").list_property_images("p1")
        self.assertNotIn("type", captured["body"])

    def test_add_images_to_property_type_360(self):
        patcher, captured = patch_urlopen(
            json.dumps({"propertyId": "p1", "type": "360", "added": [{"imageId": "s1", "url": "u", "aspectRatio": 2}], "failed": []})
        )
        with patcher:
            res = Pedra("k").add_images_to_property("p1", ["https://x/pano.jpg"], type="360")
        self.assertEqual(captured["body"]["type"], "360")
        self.assertEqual(res.type, "360")

    def test_create_virtual_tour(self):
        patcher, captured = patch_urlopen(
            json.dumps({**TOUR, "status": "processing", "progress": {"stage": "queued"}, "creditsCost": 3, "estimatedSeconds": 47, "linking": "sequential"})
        )
        with patcher:
            tour = Pedra("k").create_virtual_tour(
                [{"image_url": "https://x/entrance.jpg", "name": "Entrance"}, "https://x/kitchen.jpg"],
                name="Calle Mayor 12",
                linking="smart",
                language="es",
            )
        self.assertEqual(captured["url"], "https://app.pedra.ai/api/create_virtual_tour")
        self.assertEqual(
            captured["body"]["scenes"],
            [{"imageUrl": "https://x/entrance.jpg", "name": "Entrance"}, "https://x/kitchen.jpg"],
        )
        self.assertEqual(captured["body"]["linking"], "smart")
        self.assertEqual(captured["body"]["language"], "es")
        self.assertNotIn("propertyId", captured["body"])
        self.assertEqual(tour.tour_id, "t1")
        self.assertEqual(tour.status, "processing")
        self.assertEqual(tour.progress["stage"], "queued")
        self.assertEqual(tour.credits_cost, 3)

    def test_create_virtual_tour_from_property(self):
        patcher, captured = patch_urlopen(json.dumps({**TOUR, "status": "processing"}))
        with patcher:
            Pedra("k").create_virtual_tour(property_id="p1")
        self.assertEqual(captured["body"], {"apiKey": "k", "propertyId": "p1"})

    def test_get_virtual_tour(self):
        patcher, captured = patch_urlopen(json.dumps(TOUR))
        with patcher:
            tour = Pedra("k").get_virtual_tour("t1")
        self.assertEqual(captured["url"], "https://app.pedra.ai/api/get_virtual_tour")
        self.assertEqual(captured["body"], {"apiKey": "k", "tourId": "t1"})
        self.assertEqual(tour.tour_url, "https://app.pedra.ai/virtual-tour/t1")
        self.assertEqual(tour.embed_code, "<iframe></iframe>")
        self.assertEqual(tour.links[0]["yaw"], -18)
        self.assertEqual(tour.settings["navigationStyle"], "white")

    def test_get_virtual_tour_failed_build_is_returned_not_raised(self):
        patcher, _ = patch_urlopen(
            json.dumps({**TOUR, "status": "failed", "error": "1 of 2 scenes could not be added", "failedScenes": [{"index": 1, "error": "not 360"}]})
        )
        with patcher:
            tour = Pedra("k").get_virtual_tour("t1")
        self.assertEqual(tour.status, "failed")
        self.assertIn("could not be added", tour.error)
        self.assertEqual(tour.failed_scenes[0]["index"], 1)

    def test_list_virtual_tours(self):
        patcher, captured = patch_urlopen(json.dumps({"tours": [{"tourId": "t1", "status": "ready"}]}))
        with patcher:
            res = Pedra("k").list_virtual_tours(property_id="p1")
        self.assertEqual(captured["url"], "https://app.pedra.ai/api/list_virtual_tours")
        self.assertEqual(captured["body"]["propertyId"], "p1")
        self.assertEqual(res.tours[0]["tourId"], "t1")

    def test_update_virtual_tour_keeps_scene_id_keys(self):
        patcher, captured = patch_urlopen(json.dumps(TOUR))
        with patcher:
            Pedra("k").update_virtual_tour(
                "t1",
                scene_names={"scene_with_underscores": "Kitchen", "f1815046-aaaa": "Hall"},
                links=[{"from_scene_id": "s1", "to_scene_id": "s2", "yaw": 90}],
                navigation_style="blue",
                show_labels=True,
            )
        body = captured["body"]
        self.assertEqual(captured["url"], "https://app.pedra.ai/api/update_virtual_tour")
        self.assertEqual(body["tourId"], "t1")
        self.assertEqual(
            body["sceneNames"], {"scene_with_underscores": "Kitchen", "f1815046-aaaa": "Hall"}
        )
        self.assertEqual(body["links"], [{"fromSceneId": "s1", "toSceneId": "s2", "yaw": 90}])
        self.assertEqual(body["navigationStyle"], "blue")
        self.assertTrue(body["showLabels"])
        self.assertNotIn("sceneOrder", body)

    def test_add_virtual_tour_scenes(self):
        patcher, captured = patch_urlopen(
            json.dumps({**TOUR, "status": "processing", "addedScenes": [{"sceneId": "s3", "source": "property"}]})
        )
        with patcher:
            tour = Pedra("k").add_virtual_tour_scenes("t1", [{"image_id": "s3"}], linking="none")
        self.assertEqual(captured["url"], "https://app.pedra.ai/api/add_virtual_tour_scenes")
        self.assertEqual(captured["body"]["scenes"], [{"imageId": "s3"}])
        self.assertEqual(captured["body"]["linking"], "none")
        self.assertEqual(tour.added_scenes[0]["sceneId"], "s3")

    def test_delete_virtual_tour(self):
        patcher, captured = patch_urlopen(json.dumps({"message": "Virtual tour deleted.", "tourId": "t1"}))
        with patcher:
            res = Pedra("k").delete_virtual_tour("t1")
        self.assertEqual(captured["url"], "https://app.pedra.ai/api/delete_virtual_tour")
        self.assertEqual(res.tour_id, "t1")

    def test_create_upload_link(self):
        patcher, captured = patch_urlopen(
            json.dumps({"uploadUrl": "https://app.pedra.ai/upload/tok", "propertyId": "p9", "propertyName": "Calle Mayor 12", "expiresAt": "2026-10-01T15:26:30.687Z"})
        )
        with patcher:
            res = Pedra("k").create_upload_link(name="Calle Mayor 12", language="es")
        self.assertEqual(captured["url"], "https://app.pedra.ai/api/create_upload_link")
        self.assertEqual(captured["body"]["language"], "es")
        self.assertEqual(res.upload_url, "https://app.pedra.ai/upload/tok")
        self.assertEqual(res.property_id, "p9")

    def test_tour_409_raises_with_body(self):
        err = urllib.error.HTTPError(
            "https://app.pedra.ai/api/create_virtual_tour", 409, "Conflict", {},
            io.BytesIO(json.dumps({"error": "This property already has a virtual tour", "code": "tour_exists", "tourId": "t1"}).encode()),
        )
        with mock.patch("urllib.request.urlopen", side_effect=err):
            with self.assertRaises(PedraAPIError) as ctx:
                Pedra("k").create_virtual_tour(property_id="p1")
        self.assertEqual(ctx.exception.status, 409)
        self.assertEqual(ctx.exception.body["code"], "tour_exists")

    def test_wait_for_virtual_tour_polls_until_ready(self):
        patcher, calls = patch_urlopen_sequence(
            [
                json.dumps({**TOUR, "status": "processing", "progress": {"stage": "importing"}}),
                json.dumps({**TOUR, "status": "processing", "progress": {"stage": "linking"}}),
                json.dumps(TOUR),
            ]
        )
        with patcher, mock.patch("time.sleep") as sleep:
            tour = Pedra("k").wait_for_virtual_tour("t1", interval=2)
        self.assertEqual(len(calls), 3)
        self.assertEqual(tour.status, "ready")
        self.assertEqual(sleep.call_count, 2)
        sleep.assert_called_with(2)

    def test_wait_for_virtual_tour_returns_failed(self):
        patcher, _ = patch_urlopen(json.dumps({**TOUR, "status": "failed", "error": "The build failed."}))
        with patcher:
            tour = Pedra("k").wait_for_virtual_tour("t1", interval=0)
        self.assertEqual(tour.status, "failed")

    def test_wait_for_virtual_tour_times_out(self):
        patcher, _ = patch_urlopen(json.dumps({**TOUR, "status": "processing"}))
        with patcher:
            with self.assertRaises(PedraError):
                Pedra("k").wait_for_virtual_tour("t1", interval=0.01, timeout=0.03)


class LocalPanoramaTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="pedra-py-")

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def _file(self, name, size):
        path = os.path.join(self.dir, name)
        with open(path, "wb") as fh:
            fh.write(b"\x07" * size)
        return path

    def test_batches_ten_per_call_in_order(self):
        files = [self._file(f"pano{i:02d}.jpg", 30) for i in range(12)]
        patcher, calls = patch_urlopen_panoramas()
        with patcher:
            res = Pedra("k").add_local_panoramas("p1", files)
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[0]["url"], "https://app.pedra.ai/api/add_images_to_property")
        self.assertEqual(calls[0]["body"]["type"], "360")
        self.assertEqual(len(calls[0]["body"]["imageUrls"]), 10)
        self.assertEqual(len(calls[1]["body"]["imageUrls"]), 2)
        self.assertTrue(calls[0]["body"]["imageUrls"][0].startswith("data:image/jpeg;base64,"))
        self.assertEqual([a["path"] for a in res.added], files)
        self.assertEqual(res.type, "360")

    def test_splits_by_size_and_rejects_locally(self):
        a = self._file("a.jpg", 600)
        b = self._file("b.png", 600)
        big = self._file("c.webp", 3000)
        txt = self._file("d.txt", 10)
        missing = os.path.join(self.dir, "missing.jpg")
        patcher, calls = patch_urlopen_panoramas()
        with patcher:
            res = Pedra("k").add_local_panoramas(
                "p1", [a, b, big, txt, missing], max_request_bytes=1024
            )
        self.assertEqual(len(calls), 2)
        self.assertTrue(calls[1]["body"]["imageUrls"][0].startswith("data:image/png;base64,"))
        self.assertEqual([x["path"] for x in res.added], [a, b])
        errors = {os.path.basename(f["path"]): f["error"] for f in res.failed}
        self.assertIn("too large to send inline", errors["c.webp"])
        self.assertIn("Unsupported file type", errors["d.txt"])
        self.assertIn("Could not read file", errors["missing.jpg"])

    def test_maps_api_rejection_to_its_file(self):
        flat = self._file("flat.jpg", 20)
        patcher, _ = patch_urlopen(
            json.dumps({"propertyId": "p1", "type": "360", "added": [], "failed": [{"url": "data: URI", "error": "this is not a 360° photo"}]})
        )
        with patcher:
            res = Pedra("k").add_local_panoramas("p1", [flat])
        self.assertEqual(res.failed[0]["path"], flat)
        self.assertEqual(res.failed[0]["url"], flat)
        self.assertIn("not a 360", res.failed[0]["error"])

    def test_rejects_a_single_string(self):
        with self.assertRaises(PedraError):
            Pedra("k").add_local_panoramas("p1", "one.jpg")


class CamelizeTests(unittest.TestCase):
    def test_to_camel_keys_only(self):
        self.assertEqual(
            _camelize({"image_url": "x", "preserve_original_framing": True}),
            {"imageUrl": "x", "preserveOriginalFraming": True},
        )

    def test_drops_none_values(self):
        self.assertEqual(_camelize({"a_b": None, "c_d": 1}), {"cD": 1})


def http_error(path, status, body):
    return urllib.error.HTTPError(
        f"https://app.pedra.ai/api{path}", status, "Error", {},
        io.BytesIO(json.dumps(body).encode()),
    )


APPROVED = {
    "status": "approved",
    "apiKey": "new-key",
    "email": "ana@agency.com",
    "newAccount": True,
    "plan": "free",
    "creditsRemaining": 0,
    "appUrl": "https://app.pedra.ai",
    "note": "This account has no credits yet.",
}


class UploadLinkLimitTests(unittest.TestCase):
    def test_create_upload_link_type_and_max_files(self):
        patcher, captured = patch_urlopen(
            json.dumps({"uploadUrl": "https://app.pedra.ai/upload/tok", "propertyId": "p9", "type": "360", "maxFiles": 100})
        )
        with patcher:
            res = Pedra("k").create_upload_link(property_id="p9", type="360")
        self.assertEqual(captured["body"], {"apiKey": "k", "propertyId": "p9", "type": "360"})
        self.assertEqual(res.type, "360")
        self.assertEqual(res.max_files, 100)

    def test_upload_link_limit_429_exposes_code(self):
        body = {"error": "This account can make 5 upload links a day.", "code": "upload_link_limit"}
        with mock.patch("urllib.request.urlopen", side_effect=http_error("/create_upload_link", 429, body)):
            with self.assertRaises(PedraAPIError) as ctx:
                Pedra("k").create_upload_link()
        self.assertEqual(ctx.exception.status, 429)
        self.assertEqual(ctx.exception.code, "upload_link_limit")
        self.assertEqual(ctx.exception.body, body)

    def test_upload_limit_429_exposes_code(self):
        body = {"error": "Daily upload limit reached", "code": "upload_limit"}
        with mock.patch("urllib.request.urlopen", side_effect=http_error("/add_images_to_property", 429, body)):
            with self.assertRaises(PedraAPIError) as ctx:
                Pedra("k").add_images_to_property("p1", ["https://x/1.jpg"])
        self.assertEqual(ctx.exception.code, "upload_limit")

    def test_error_without_code(self):
        self.assertIsNone(PedraAPIError("x", status=403, body={"error": "x"}).code)
        self.assertIsNone(PedraAPIError("x", status=500, body=None).code)


class AccessTests(unittest.TestCase):
    def test_request_access_needs_no_api_key(self):
        patcher, captured = patch_urlopen(
            json.dumps({"requestId": "r1", "status": "pending", "expiresAt": "2026-09-30T12:30:00.000Z", "pollAfterSeconds": 5, "message": "We emailed a link"})
        )
        with mock.patch.dict("os.environ", {}, clear=True), patcher:
            res = request_access("ana@agency.com", agent_name="Test agent")
        self.assertEqual(captured["url"], "https://app.pedra.ai/api/agent_signup")
        self.assertEqual(captured["body"], {"email": "ana@agency.com", "agentName": "Test agent"})
        self.assertEqual(res.request_id, "r1")
        self.assertEqual(res.status, "pending")
        self.assertEqual(res.poll_after_seconds, 5)

    def test_request_access_omits_unset_agent_name_and_honors_base_url(self):
        patcher, captured = patch_urlopen(json.dumps({"requestId": "r2", "status": "pending"}))
        with patcher:
            Pedra.request_access("a@b.co", base_url="http://localhost:3000/api/")
        self.assertEqual(captured["url"], "http://localhost:3000/api/agent_signup")
        self.assertEqual(captured["body"], {"email": "a@b.co"})

    def test_request_access_requires_email(self):
        with self.assertRaises(PedraError):
            request_access("")

    def test_request_access_errors_keep_code_and_body(self):
        for status, code in ((400, "disposable_email"), (429, "rate_limited"), (503, "unavailable")):
            body = {"error": "nope", "code": code}
            with mock.patch("urllib.request.urlopen", side_effect=http_error("/agent_signup", status, body)):
                with self.assertRaises(PedraAPIError) as ctx:
                    request_access("a@b.co")
            self.assertEqual(ctx.exception.status, status)
            self.assertEqual(ctx.exception.code, code)
            self.assertEqual(ctx.exception.body, body)

    def test_get_access_status_approved(self):
        patcher, captured = patch_urlopen(json.dumps(APPROVED))
        with patcher:
            res = get_access_status("r1")
        self.assertEqual(captured["url"], "https://app.pedra.ai/api/agent_signup_status")
        self.assertEqual(captured["body"], {"requestId": "r1"})
        self.assertTrue(res.approved)
        self.assertEqual(res.api_key, "new-key")
        self.assertTrue(res.new_account)
        self.assertEqual(res.credits_remaining, 0)
        self.assertIn("no credits", res.note)
        self.assertNotIn("new-key", repr(res))

    def test_get_access_status_unknown_request_404(self):
        with mock.patch("urllib.request.urlopen", side_effect=http_error("/agent_signup_status", 404, {"error": "Unknown requestId"})):
            with self.assertRaises(PedraAPIError) as ctx:
                get_access_status("nope")
        self.assertEqual(ctx.exception.status, 404)

    def test_wait_for_access_polls_until_approved(self):
        patcher, calls = patch_urlopen_sequence(
            [json.dumps({"status": "pending"}), json.dumps({"status": "pending"}), json.dumps(APPROVED)]
        )
        with patcher, mock.patch("time.sleep") as sleep:
            res = wait_for_access("r1", interval=0.01)
        self.assertEqual(len(calls), 3)
        self.assertEqual(sleep.call_count, 2)
        self.assertEqual(res.api_key, "new-key")

    def test_wait_for_access_returns_denied_and_expired(self):
        for status in ("denied", "expired"):
            patcher, _ = patch_urlopen_sequence([json.dumps({"status": "pending"}), json.dumps({"status": status})])
            with patcher, mock.patch("time.sleep"):
                res = Pedra.wait_for_access("r1", interval=0.01)
            self.assertEqual(res.status, status)
            self.assertFalse(res.approved)
            self.assertIsNone(res.api_key)

    def test_wait_for_access_times_out(self):
        patcher, _ = patch_urlopen_sequence([json.dumps({"status": "pending"})])
        with patcher:
            with self.assertRaises(PedraError) as ctx:
                wait_for_access("r1", interval=1.0, timeout=0.01)
        self.assertIn("still pending", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
