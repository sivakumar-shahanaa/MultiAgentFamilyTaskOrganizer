from sqlmodel import Session

from app.integrations.weather import WeatherIntegration
from app.integrations.calendar import CalendarIntegration
from app.integrations.spotify import JamStore, SpotifyCreateJamIntegration, SpotifyAddToJamIntegration

_jam_store = JamStore()  # shared so create and add-to see the same jams

INTEGRATIONS = {
    "weather": WeatherIntegration(),
    "reschedule_calendar": CalendarIntegration(),
    "spotify_create_jam": SpotifyCreateJamIntegration(_jam_store),
    "spotify_add_to_jam": SpotifyAddToJamIntegration(_jam_store),
}


async def run_action(action_type: str, params: dict, session: Session) -> dict:
    integration = INTEGRATIONS.get(action_type)
    if integration is None:
        return {"status": "error", "message": f"no integration for '{action_type}'"}
    return await integration.execute(params, session)
