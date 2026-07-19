from sqlmodel import Session

from app.db.session import engine
from app.integrations.base import Integration
from app.integrations.spotify_client import add_to_queue, get_valid_access_token, search_track


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

        queued = add_to_queue(track["uri"], access_token)
        if not queued:
            return {
                "status": "queue_failed",
                "track": track,
                "message": "No active Spotify device found. Open Spotify on a phone or desktop first.",
            }

        return {"status": "queued", "track": track}
