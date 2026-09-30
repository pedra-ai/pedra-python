# Changelog

## 0.4.0

- **Virtual tours.** New methods for the Virtual Tour API:
  `create_virtual_tour`, `get_virtual_tour`, `list_virtual_tours`,
  `update_virtual_tour`, `add_virtual_tour_scenes`, `delete_virtual_tour`, and
  `create_upload_link`, returning typed dataclasses (`VirtualTour`,
  `VirtualToursResponse`, `DeleteVirtualTourResponse`, `UploadLinkResponse`).
  `TourSceneInput` / `TourLinkInput` TypedDicts document the input shapes.
- `wait_for_virtual_tour(tour_id, interval=, timeout=)` polls until the tour is
  `ready` or `failed` (a failed build is returned with `status == "failed"` and
  `error`; it isn't raised).
- `add_local_panoramas(property_id, paths)`: uploads 360° photo files from disk
  as base64 `data:` URIs, in order, batched under the API's 10-per-call and
  50 MB body limits. Unsendable files are reported in `failed`.
- `list_property_images` and `add_images_to_property` accept `type="photo" | "360"`.
- `generate_voice` accepts `voice_id`; `music_library` returns `voices_by_language`.
- **Agent signup, no API key needed.** `request_access(email, agent_name=)`,
  `get_access_status(request_id)` and `wait_for_access(request_id, interval=,
  timeout=)` (also as `Pedra.request_access` etc.), returning `AccessRequest` /
  `AccessStatus`: Pedra emails the person a confirmation link, and the approved
  status carries the new `api_key`. `wait_for_access` returns `denied` /
  `expired` rather than raising.
- `create_upload_link` accepts `type="any" | "360"` (default `"any"`: regular
  photos and 360° photos) and returns `type` and `max_files`.
- `PedraAPIError.code` exposes the response's `code` (e.g. `upload_limit`,
  `upload_link_limit`, `rate_limited`, `tour_exists`).

## 0.1.0

- Initial release.
- Full coverage of the Pedra API: `enhance`, `enhance_and_correct_perspective`,
  `empty`, `furnish`, `renovation`, `edit_via_prompt`, `sky`, `remove`, `blur`,
  `create_video`, `credits`, `feedback`.
- Zero runtime dependencies (standard library only), typed dataclass responses,
  and typed errors (`PedraError`, `PedraAPIError`).
