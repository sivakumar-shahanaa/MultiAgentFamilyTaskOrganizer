from app.integrations.weather import WeatherIntegration
from app.integrations.calendar import CalendarIntegration
from app.integrations.spotify import SpotifyIntegration

INTEGRATIONS = {
    "weather": WeatherIntegration(),
    "reschedule_calendar": CalendarIntegration(),
    "spotify_play": SpotifyIntegration(),
}


def run_action(action_type: str, params: dict) -> dict:
    integration = INTEGRATIONS.get(action_type)
    if integration is None:
        return {"status": "error", "message": f"no integration for '{action_type}'"}
    return integration.execute(params)
