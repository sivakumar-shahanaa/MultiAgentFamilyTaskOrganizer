from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from sqlmodel import Session

from app.db.session import get_session
from app.integrations.spotify_client import (
    HOUSEHOLD_SPOTIFY_ACCOUNT_ID,
    build_authorize_url,
    exchange_code_for_tokens,
)
from app.models import SpotifyCredential

router = APIRouter(prefix="/spotify", tags=["spotify-auth"])


@router.get("/login")
def spotify_login(person_id: str | None = None):
    """Connect the shared household Spotify account.

    person_id is accepted only for backward-compatible old links and is ignored.
    """
    return RedirectResponse(build_authorize_url(state=HOUSEHOLD_SPOTIFY_ACCOUNT_ID))


@router.get("/callback")
def spotify_callback(code: str, state: str, session: Session = Depends(get_session)):
    if state != HOUSEHOLD_SPOTIFY_ACCOUNT_ID:
        raise HTTPException(status_code=400, detail="Invalid Spotify OAuth state")

    try:
        token_data = exchange_code_for_tokens(code)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Spotify token exchange failed: {exc}")

    expires_at = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(
        seconds=token_data.get("expires_in", 3600)
    )
    existing = session.get(SpotifyCredential, HOUSEHOLD_SPOTIFY_ACCOUNT_ID)
    if existing:
        existing.access_token = token_data["access_token"]
        existing.refresh_token = token_data.get("refresh_token", existing.refresh_token)
        existing.expires_at = expires_at
        session.add(existing)
    else:
        session.add(
            SpotifyCredential(
                account_id=HOUSEHOLD_SPOTIFY_ACCOUNT_ID,
                access_token=token_data["access_token"],
                refresh_token=token_data["refresh_token"],
                expires_at=expires_at,
            )
        )
    session.commit()
    return {"status": "connected", "account_id": HOUSEHOLD_SPOTIFY_ACCOUNT_ID}
