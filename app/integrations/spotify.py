from sqlmodel import Session

from app.db.session import engine
from app.integrations.base import Integration
from app.integrations.spotify_client import (
    add_to_queue,
    get_available_devices,
    get_valid_access_token,
    search_track,
    transfer_playback,
)


class SpotifyIntegration(Integration):
    """Queue a requested track on the authenticated person's Spotify account."""

    def execute(self, params: dict) -> dict:
        query = params.get("track") or params.get("query") or ""
        if not query:
            return {"status": "error", "message": "missing track query"}

        with Session(engine) as session:
            access_token = get_valid_access_token(session)

        if access_token is None:
            return {
                "status": "needs_spotify_auth",
                "message": "Connect Spotify first: /spotify/login",
            }

        track = search_track(query, access_token)
        if track is None:
            return {"status": "no_match", "query": query}

        devices = get_available_devices(access_token)
        active_device = next((device for device in devices if device.get("is_active")), None)
        target_device = active_device or (devices[0] if devices else None)
        if target_device is None:
            return {
                "status": "no_device",
                "track": track,
                "message": "No Spotify device is available. Open Spotify on a phone or desktop first.",
            }

        device_id = target_device.get("id")
        activated_device = False
        if active_device is None and device_id:
            activated_device = transfer_playback(device_id, access_token)

        queued = add_to_queue(track["uri"], access_token, device_id=device_id)
        if not queued:
            return {
                "status": "queue_failed",
                "track": track,
                "device": target_device.get("name"),
                "message": "Spotify did not accept the queue request. Try pressing play in Spotify once, then ask again.",
            }

        return {
            "status": "queued",
            "track": track,
            "device": target_device.get("name"),
            "activated_device": activated_device,
        }
