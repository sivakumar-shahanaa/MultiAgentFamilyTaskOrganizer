import os
from datetime import datetime, timedelta

import httpx
from sqlmodel import Session

from app.models import SpotifyCredential

SPOTIFY_CLIENT_ID = os.environ.get("SPOTIFY_CLIENT_ID", "")
SPOTIFY_CLIENT_SECRET = os.environ.get("SPOTIFY_CLIENT_SECRET", "")
SPOTIFY_REDIRECT_URI = os.environ.get("SPOTIFY_REDIRECT_URI", "http://127.0.0.1:8000/spotify/callback")

AUTHORIZE_URL = "https://accounts.spotify.com/authorize"
TOKEN_URL = "https://accounts.spotify.com/api/token"
API_BASE = "https://api.spotify.com/v1"

# Scopes needed: search doesn't require auth, but queueing/playing on the
# host's device does.
SCOPES = "user-modify-playback-state user-read-playback-state"


def build_authorize_url(state: str) -> str:
    params = {
        "client_id": SPOTIFY_CLIENT_ID,
        "response_type": "code",
        "redirect_uri": SPOTIFY_REDIRECT_URI,
        "scope": SCOPES,
        "state": state,
    }
    query = "&".join(f"{k}={httpx.QueryParams({k: v})[k]}" for k, v in params.items())
    return f"{AUTHORIZE_URL}?{query}"


async def exchange_code_for_tokens(code: str) -> dict:
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            TOKEN_URL,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": SPOTIFY_REDIRECT_URI,
            },
            auth=(SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET),
        )
        resp.raise_for_status()
        return resp.json()


async def refresh_access_token(refresh_token: str) -> dict:
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            TOKEN_URL,
            data={
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
            },
            auth=(SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET),
        )
        resp.raise_for_status()
        return resp.json()


async def get_valid_access_token(profile_id: str, session: Session) -> str | None:
    """Returns a usable access token for this profile, refreshing if expired.
    Returns None if the profile has never connected Spotify.
    """
    cred = session.get(SpotifyCredential, profile_id)
    if cred is None:
        return None

    if cred.expires_at > datetime.utcnow():
        return cred.access_token

    token_data = await refresh_access_token(cred.refresh_token)
    cred.access_token = token_data["access_token"]
    cred.expires_at = datetime.utcnow() + timedelta(seconds=token_data.get("expires_in", 3600))
    # Spotify only returns a new refresh_token sometimes -- keep the old one otherwise.
    if "refresh_token" in token_data:
        cred.refresh_token = token_data["refresh_token"]
    session.add(cred)
    session.commit()
    return cred.access_token


async def search_track(query: str, access_token: str) -> dict | None:
    """Searches the Spotify catalog and returns the top track match, or None."""
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{API_BASE}/search",
            params={"q": query, "type": "track", "limit": 1},
            headers={"Authorization": f"Bearer {access_token}"},
        )
        resp.raise_for_status()
        items = resp.json().get("tracks", {}).get("items", [])
        if not items:
            return None
        track = items[0]
        return {
            "uri": track["uri"],
            "name": track["name"],
            "artist": ", ".join(a["name"] for a in track["artists"]),
        }


async def add_to_queue(track_uri: str, access_token: str) -> bool:
    """Adds a track to the host's active-device queue. Returns False if
    there's no active device (common failure -- host needs Spotify open
    on some device).
    """
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{API_BASE}/me/player/queue",
            params={"uri": track_uri},
            headers={"Authorization": f"Bearer {access_token}"},
        )
        return resp.status_code == 204
