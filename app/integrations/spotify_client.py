import os
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import httpx
from sqlmodel import Session

from app.models import SpotifyCredential

SPOTIFY_CLIENT_ID = os.environ.get("SPOTIFY_CLIENT_ID", "")
SPOTIFY_CLIENT_SECRET = os.environ.get("SPOTIFY_CLIENT_SECRET", "")
SPOTIFY_REDIRECT_URI = os.environ.get(
    "SPOTIFY_REDIRECT_URI",
    "http://127.0.0.1:8000/spotify/callback",
)

AUTHORIZE_URL = "https://accounts.spotify.com/authorize"
TOKEN_URL = "https://accounts.spotify.com/api/token"
API_BASE = "https://api.spotify.com/v1"
SCOPES = "user-modify-playback-state user-read-playback-state"


def build_authorize_url(state: str) -> str:
    params = {
        "client_id": SPOTIFY_CLIENT_ID,
        "response_type": "code",
        "redirect_uri": SPOTIFY_REDIRECT_URI,
        "scope": SCOPES,
        "state": state,
    }
    return f"{AUTHORIZE_URL}?{urlencode(params)}"


def exchange_code_for_tokens(code: str) -> dict:
    with httpx.Client(timeout=20) as client:
        response = client.post(
            TOKEN_URL,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": SPOTIFY_REDIRECT_URI,
            },
            auth=(SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET),
        )
        response.raise_for_status()
        return response.json()


def refresh_access_token(refresh_token: str) -> dict:
    with httpx.Client(timeout=20) as client:
        response = client.post(
            TOKEN_URL,
            data={
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
            },
            auth=(SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET),
        )
        response.raise_for_status()
        return response.json()


HOUSEHOLD_SPOTIFY_ACCOUNT_ID = "household"


def get_valid_access_token(session: Session) -> str | None:
    credential = session.get(SpotifyCredential, HOUSEHOLD_SPOTIFY_ACCOUNT_ID)
    if credential is None:
        return None

    if credential.expires_at > _now():
        return credential.access_token

    token_data = refresh_access_token(credential.refresh_token)
    credential.access_token = token_data["access_token"]
    credential.expires_at = _now() + timedelta(seconds=token_data.get("expires_in", 3600))
    if "refresh_token" in token_data:
        credential.refresh_token = token_data["refresh_token"]
    session.add(credential)
    session.commit()
    return credential.access_token


def search_track(query: str, access_token: str) -> dict | None:
    with httpx.Client(timeout=20) as client:
        response = client.get(
            f"{API_BASE}/search",
            params={"q": query, "type": "track", "limit": 1},
            headers={"Authorization": f"Bearer {access_token}"},
        )
        response.raise_for_status()
        items = response.json().get("tracks", {}).get("items", [])
        if not items:
            return None
        track = items[0]
        return {
            "uri": track["uri"],
            "name": track["name"],
            "artist": ", ".join(artist["name"] for artist in track["artists"]),
        }


def get_available_devices(access_token: str) -> list[dict]:
    with httpx.Client(timeout=20) as client:
        response = client.get(
            f"{API_BASE}/me/player/devices",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        response.raise_for_status()
        return response.json().get("devices", [])


def transfer_playback(device_id: str, access_token: str) -> bool:
    with httpx.Client(timeout=20) as client:
        response = client.put(
            f"{API_BASE}/me/player",
            json={"device_ids": [device_id], "play": False},
            headers={"Authorization": f"Bearer {access_token}"},
        )
        return response.status_code in {202, 204}


def add_to_queue(track_uri: str, access_token: str, device_id: str | None = None) -> bool:
    params = {"uri": track_uri}
    if device_id is not None:
        params["device_id"] = device_id
    with httpx.Client(timeout=20) as client:
        response = client.post(
            f"{API_BASE}/me/player/queue",
            params=params,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        return response.status_code == 204


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)
