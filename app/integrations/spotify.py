from sqlmodel import Session

from app.integrations.base import Integration
from app.integrations.spotify_client import (
    get_valid_access_token,
    search_track,
    add_to_queue,
)


class JamStore:
    """Tracks which profile is hosting each jam and what's been requested.
    The actual playback happens on the host's real Spotify account -- this
    is just bookkeeping for who owns which jam and a log of what was queued.
    """

    def __init__(self):
        self._jams: dict[str, dict] = {}

    def create(self, host_profile_id: str) -> str:
        import uuid
        jam_id = str(uuid.uuid4())[:8]
        self._jams[jam_id] = {"host_id": host_profile_id, "queue": []}
        return jam_id

    def get(self, jam_id: str) -> dict | None:
        return self._jams.get(jam_id)

    def record_request(self, jam_id: str, track_name: str) -> None:
        jam = self._jams.get(jam_id)
        if jam is not None:
            jam["queue"].append(track_name)


class SpotifyCreateJamIntegration(Integration):
    """Starts a jam. Parent-only via the permission table. Requires the
    host to have already connected Spotify via /spotify/login.
    """

    def __init__(self, store: JamStore):
        self.store = store

    async def execute(self, params: dict, session: Session) -> dict:
        host_id = params.get("profile_id")
        token = await get_valid_access_token(host_id, session)
        if token is None:
            return {
                "status": "needs_spotify_auth",
                "message": f"{host_id} hasn't connected Spotify yet. Visit /spotify/login?profile_id={host_id}",
            }
        jam_id = self.store.create(host_id)
        return {"status": "created", "jam_id": jam_id, "host_id": host_id}


class SpotifyAddToJamIntegration(Integration):
    """Adds a track to an existing jam. Parent/kid/guest can all do this --
    the request is searched against the real Spotify catalog and queued
    onto the jam host's authenticated playback session.

    params: {"jam_id": ..., "query": "Espresso Sabrina Carpenter"}
    `query` is free text -- this is the hook point for an LLM to fill in
    later ("play that Sabrina Carpenter song from the summer" -> query).
    """

    def __init__(self, store: JamStore):
        self.store = store

    async def execute(self, params: dict, session: Session) -> dict:
        jam_id = params.get("jam_id")
        query = params.get("query", "")

        jam = self.store.get(jam_id)
        if jam is None:
            return {"status": "not_found", "jam_id": jam_id}

        host_token = await get_valid_access_token(jam["host_id"], session)
        if host_token is None:
            return {"status": "host_needs_spotify_auth", "host_id": jam["host_id"]}

        track = await search_track(query, host_token)
        if track is None:
            return {"status": "no_match", "query": query}

        queued = await add_to_queue(track["uri"], host_token)
        if not queued:
            return {
                "status": "queue_failed",
                "track": track,
                "message": "No active Spotify device on the host's account -- open Spotify on a phone/desktop first.",
            }

        self.store.record_request(jam_id, f"{track['name']} - {track['artist']}")
        return {"status": "queued", "jam_id": jam_id, "track": track}
