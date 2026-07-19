from app.integrations.base import Integration


class WeatherIntegration(Integration):
    """Stub for local weather / clothing advice. Replace `execute` with a
    real OpenWeather (or similar) call later -- keep the return shape.
    """

    def execute(self, params: dict) -> dict:
        location = params.get("location", "home")
        return {
            "location": location,
            "temp_f": 68,
            "condition": "cloudy",
            "advice": "bring a light jacket",
        }
