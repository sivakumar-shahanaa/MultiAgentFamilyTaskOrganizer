from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from sqlmodel import Session

from app.db import Person
from app.db.session import get_session
from app.integrations.spotify_client import build_authorize_url, exchange_code_for_tokens
from app.models import SpotifyCredential

router = APIRouter(prefix="/spotify", tags=["spotify-auth"])


@router.get("/login")
def spotify_login(person_id: str, session: Session = Depends(get_session)):
    person = session.get(Person, person_id)
    if person is None:
        raise HTTPException(status_code=404, detail="Person not found")
    return RedirectResponse(build_authorize_url(state=person_id))


@router.get("/callback")
def spotify_callback(code: str, state: str, session: Session = Depends(get_session)):
    person_id = state
    if session.get(Person, person_id) is None:
        raise HTTPException(status_code=404, detail="Person not found")

    try:
        token_data = exchange_code_for_tokens(code)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Spotify token exchange failed: {exc}")

    expires_at = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(
        seconds=token_data.get("expires_in", 3600)
    )
    existing = session.get(SpotifyCredential, person_id)
    if existing:
        existing.access_token = token_data["access_token"]
        existing.refresh_token = token_data.get("refresh_token", existing.refresh_token)
        existing.expires_at = expires_at
        session.add(existing)
    else:
        session.add(
            SpotifyCredential(
                person_id=person_id,
                access_token=token_data["access_token"],
                refresh_token=token_data["refresh_token"],
                expires_at=expires_at,
            )
        )
    session.commit()
    return {"status": "connected", "person_id": person_id}
