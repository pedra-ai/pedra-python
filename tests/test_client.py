"""Tests for the Pedra Python client.

Run with: python -m unittest discover -s tests
"""

import json
import unittest
from unittest import mock

from pedra import Pedra, PedraAPIError, PedraError
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


class CamelizeTests(unittest.TestCase):
    def test_to_camel_keys_only(self):
        self.assertEqual(
            _camelize({"image_url": "x", "preserve_original_framing": True}),
            {"imageUrl": "x", "preserveOriginalFraming": True},
        )

    def test_drops_none_values(self):
        self.assertEqual(_camelize({"a_b": None, "c_d": 1}), {"cD": 1})


if __name__ == "__main__":
    unittest.main()
