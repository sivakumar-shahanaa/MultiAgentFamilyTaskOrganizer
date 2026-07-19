from app.integrations.weather import WeatherIntegration
from app.integrations.calendar import CalendarIntegration
from app.integrations.spotify import SpotifyIntegration

INTEGRATIONS = {
    "weather": WeatherIntegration(),
    "read_schedule": CalendarIntegration(),
    "write_schedule": CalendarIntegration(),
    "spotify_play": SpotifyIntegration(),
}


def run_action(action_type: str, params: dict) -> dict:
    integration = INTEGRATIONS.get(action_type)
    if integration is None:
        return {"status": "error", "message": f"no integration for '{action_type}'"}

    if action_type == "read_schedule":
        params = {**params, "action": "list"}
    if params.get("action") == "error":
        return {"status": "error", "message": params.get("message", "invalid action params")}

    return integration.execute(params)
