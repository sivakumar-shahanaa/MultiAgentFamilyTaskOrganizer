from app.integrations.base import Integration


class SpotifyIntegration(Integration):
    """Stub for Spotify playback control. Replace `execute` with real
    Spotify Web API calls later -- keep the return shape.
    """

    def execute(self, params: dict) -> dict:
        track = params.get("track", "Unknown")
        return {"now_playing": track, "status": "playing"}
