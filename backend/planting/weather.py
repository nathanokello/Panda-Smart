"""Live weather data for planting advice. No AI here: data in, numbers out.

Sources (checked 18 November 2026; re-check terms before a commercial launch):
- NASA POWER daily point API: free, no key, daily data since 1981 at roughly
  55 km resolution. Used for rainfall history, which drives the advice rules.
  https://power.larc.nasa.gov/docs/services/api/temporal/daily/
- Open-Meteo forecast API: free, no key, but ONLY for non-commercial use (under
  10,000 calls a day, data CC BY 4.0). Panda Smart sells subscriptions, so a
  paid plan or a self-hosted server is needed before commercial use. Off by
  default: set OPEN_METEO_ENABLED=1 for a demo.
  https://open-meteo.com/en/terms

Both functions use only the standard library, so no new packages are needed.
"""
import json
from datetime import date
from http.client import HTTPException
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

NASA_POWER_URL = "https://power.larc.nasa.gov/api/temporal/daily/point"
OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
NASA_MISSING = -999  # POWER's fill value for days without data
TIMEOUT_SECONDS = 20


class WeatherSourceError(Exception):
    """The weather service could not be reached or returned something unexpected."""


def _get_json(url: str, params: dict) -> dict:
    request = Request(f"{url}?{urlencode(params)}", headers={"User-Agent": "PandaSmart/1.0"})
    try:
        with urlopen(request, timeout=TIMEOUT_SECONDS) as response:  # noqa: S310 (fixed https hosts)
            return json.loads(response.read().decode("utf-8"))
    except (URLError, OSError, HTTPException, ValueError) as exc:
        # OSError covers resets and timeouts that urllib does not wrap in URLError.
        raise WeatherSourceError(f"{url}: {exc}") from exc


def parse_nasa_power_rainfall(payload: dict) -> list:
    """Return [(date, rainfall_mm)] from a POWER daily response, skipping missing days."""
    try:
        series = payload["properties"]["parameter"]["PRECTOTCORR"]
    except (KeyError, TypeError) as exc:
        raise WeatherSourceError("NASA POWER response has no PRECTOTCORR series.") from exc
    rows = []
    for key, value in sorted(series.items()):
        if value is None or float(value) <= NASA_MISSING:
            continue
        rows.append((date(int(key[:4]), int(key[4:6]), int(key[6:8])), round(float(value), 2)))
    return rows


def fetch_nasa_power_rainfall(lat: float, lng: float, start: date, end: date) -> list:
    """Daily corrected precipitation (mm/day) for one point."""
    payload = _get_json(NASA_POWER_URL, {
        "parameters": "PRECTOTCORR",
        "community": "AG",
        "latitude": f"{lat:.4f}",
        "longitude": f"{lng:.4f}",
        "start": start.strftime("%Y%m%d"),
        "end": end.strftime("%Y%m%d"),
        "format": "JSON",
    })
    return parse_nasa_power_rainfall(payload)


def parse_open_meteo_daily(payload: dict) -> list:
    """Return a list of day dicts from an Open-Meteo daily forecast response."""
    try:
        daily = payload["daily"]
        days = daily["time"]
    except (KeyError, TypeError) as exc:
        raise WeatherSourceError("Open-Meteo response has no daily forecast.") from exc

    def column(name):
        values = daily.get(name) or [None] * len(days)
        return values + [None] * (len(days) - len(values))

    rain, tmax, tmin, chance = (column(n) for n in (
        "precipitation_sum", "temperature_2m_max", "temperature_2m_min",
        "precipitation_probability_max"))
    return [
        {"date": day, "rain_mm": rain[i], "temp_max_c": tmax[i], "temp_min_c": tmin[i],
         "rain_chance_pct": chance[i]}
        for i, day in enumerate(days)
    ]


def fetch_open_meteo_forecast(lat: float, lng: float, days: int = 7) -> list:
    payload = _get_json(OPEN_METEO_URL, {
        "latitude": f"{lat:.4f}",
        "longitude": f"{lng:.4f}",
        "daily": "precipitation_sum,temperature_2m_max,temperature_2m_min,precipitation_probability_max",
        "timezone": "Africa/Nairobi",
        "forecast_days": days,
    })
    return parse_open_meteo_daily(payload)
