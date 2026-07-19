from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from sqlmodel import Session

from app.db.session import get_session
from app.integrations.spotify_client import build_authorize_url, exchange_code_for_tokens
from app.models import SpotifyCredential

router = APIRouter(prefix="/spotify", tags=["spotify-auth"])


@router.get("/login")
def spotify_login(profile_id: str):
    """Redirect the browser to Spotify's consent screen. `state` carries the
    profile_id through the OAuth round trip so /callback knows who to save
    the tokens for.
    """
    return RedirectResponse(build_authorize_url(state=profile_id))


@router.get("/callback")
async def spotify_callback(code: str, state: str, session: Session = Depends(get_session)):
    """Spotify redirects here after the user approves access. `state` is the
    profile_id we passed in at /login.
    """
    profile_id = state
    try:
        token_data = await exchange_code_for_tokens(code)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Spotify token exchange failed: {exc}")

    expires_at = datetime.utcnow() + timedelta(seconds=token_data.get("expires_in", 3600))

    existing = session.get(SpotifyCredential, profile_id)
    if existing:
        existing.access_token = token_data["access_token"]
        existing.refresh_token = token_data.get("refresh_token", existing.refresh_token)
        existing.expires_at = expires_at
        session.add(existing)
    else:
        session.add(
            SpotifyCredential(
                profile_id=profile_id,
                access_token=token_data["access_token"],
                refresh_token=token_data["refresh_token"],
                expires_at=expires_at,
            )
        )
    session.commit()

    return {"status": "connected", "profile_id": profile_id}
