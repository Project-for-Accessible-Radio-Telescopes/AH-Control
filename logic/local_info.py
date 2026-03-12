# Obtain local information, such as long, lat, timezone, and elevation, using geopy and timezonefinder
# Also, obtain Sidereal Time using astropy and compute the Local Hour Angle of the Sun and the Galactic Center

import json
from urllib import request, error

from geopy.geocoders import Nominatim
from timezonefinder import TimezoneFinder
from astropy.time import Time
from astropy.coordinates import EarthLocation, AltAz, SkyCoord, get_sun
import astropy.units as u
import datetime


def _fetch_json(url, timeout=6):
    req = request.Request(url, headers={"User-Agent": "parttelescopes/1.0"})
    with request.urlopen(req, timeout=timeout) as response:
        raw = response.read().decode("utf-8")
        return json.loads(raw)


def _ip_geolocation_fallback(timeout_s=6):
    providers = [
        "https://ipapi.co/json/",
        "https://ipinfo.io/json",
    ]

    for url in providers:
        try:
            payload = _fetch_json(url, timeout=timeout_s)
            if "latitude" in payload and "longitude" in payload:
                lat = float(payload["latitude"])
                lon = float(payload["longitude"])
                tz = payload.get("timezone")
                return lat, lon, tz

            if "loc" in payload:
                loc_value = str(payload["loc"])
                lat_text, lon_text = loc_value.split(",", 1)
                lat = float(lat_text.strip())
                lon = float(lon_text.strip())
                tz = payload.get("timezone")
                return lat, lon, tz
        except (ValueError, KeyError, error.URLError, TimeoutError, json.JSONDecodeError):
            continue
        except Exception:
            continue

    return None, None, None

def obtain_local_info(timeout_s=6, allow_ip_fallback=True):
    geolocator = Nominatim(user_agent="parttelescopes")

    latitude = None
    longitude = None
    timezone_str = None

    try:
        location = geolocator.geocode("me", exactly_one=True, timeout=timeout_s)
        if location is not None:
            latitude = float(location.latitude)
            longitude = float(location.longitude)
    except Exception:
        location = None

    if (latitude is None or longitude is None) and allow_ip_fallback:
        latitude, longitude, timezone_str = _ip_geolocation_fallback(timeout_s=timeout_s)

    if latitude is None or longitude is None:
        return None

    tf = TimezoneFinder()
    if not timezone_str:
        timezone_str = tf.timezone_at(lng=longitude, lat=latitude)

    if timezone_str is None:
        timezone_str = datetime.datetime.now(datetime.timezone.utc).astimezone().tzname() or "UTC"

    local_time = datetime.datetime.now(datetime.timezone.utc).astimezone().strftime('%Y-%m-%d %H:%M:%S %Z%z')

    return {
        "latitude": latitude,
        "longitude": longitude,
        "timezone": timezone_str,
        "local_time": local_time,
    }

def compute_sidereal_time_and_hour_angle(latitude, longitude):
    location = EarthLocation(lat=latitude * u.deg, lon=longitude * u.deg)
    time = Time.now()
    sidereal_time = time.sidereal_time('mean', longitude=longitude * u.deg)

    sun = get_sun(time).transform_to(AltAz(obstime=time, location=location))
    galactic_center = SkyCoord(l=0 * u.deg, b=0 * u.deg, frame='galactic').transform_to(
        AltAz(obstime=time, location=location)
    )

    return {
        "sidereal_time": sidereal_time.to_string(unit='hour'),
        "sun_altitude": sun.alt.degree,
        "sun_azimuth": sun.az.degree,
        "galactic_center_altitude": galactic_center.alt.degree,
        "galactic_center_azimuth": galactic_center.az.degree,
    }